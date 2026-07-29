"""
Sign detection wrapper (multi-backend).

Supports two interchangeable backends:
  * "onnx"  — runs the model via `onnxruntime` only (no torch/ultralytics).
              Low memory (~hundreds of MB) → ideal for Render's 512 MB free tier.
  * "torch" — runs the original .pt via Ultralytics YOLO (auto CUDA/CPU).

Selected via `MODEL_BACKEND`. Frame is LetterBoxed to 416x416 before inference.
There is NO fake/mock fallback: if the model can't be loaded, loading records a
clear error, /health reports it, and inference is rejected — results are always
real.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from backend.config import labels
from backend.config.settings import settings
from backend.inference.preprocessing import letterbox, scale_box_to_original
from backend.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Detection:
    """A single detected sign."""

    class_id: int
    class_name: str
    glyph: str
    confidence: float
    box: tuple[int, int, int, int]


@dataclass
class InferenceResult:
    """Result of running inference on one frame."""

    detections: List[Detection] = field(default_factory=list)
    latency_ms: float = 0.0
    device: str = "cpu"
    img_size: int = settings.MODEL_IMG_SIZE

    @property
    def best(self) -> Optional[Detection]:
        return max(self.detections, key=lambda d: d.confidence, default=None)


class SignDetector:
    """Singleton multi-backend detector wrapper."""

    _instance: "SignDetector | None" = None

    def __init__(self) -> None:
        self.backend = settings.MODEL_BACKEND.lower()
        self.model = None
        self.onnx = None
        self.device = "cpu"
        self.load_error: str | None = None
        try:
            self._load()
        except Exception as exc:
            self.load_error = str(exc)
            logger.error("Model load failed: %s", exc)

    @classmethod
    def instance(cls) -> "SignDetector":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------ loading
    def _load(self) -> None:
        if self.backend == "onnx":
            self._load_onnx()
        elif self.backend == "torch":
            self._load_torch()
        else:
            raise RuntimeError(
                f"Invalid MODEL_BACKEND '{self.backend}'. Use 'onnx' or 'torch'."
            )

    def _load_onnx(self) -> None:
        from backend.inference.onnx_backend import OnnxDetector

        try:
            self.onnx = OnnxDetector(settings.ONNX_MODEL_PATH)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "ONNX model file not found at "
                f"'{settings.ONNX_MODEL_PATH}'. Export your weights with "
                "`python scripts/export_onnx.py --weights backend/models/yolov26s.pt` "
                "and set ONNX_MODEL_PATH in your .env."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to load ONNX model: {exc}") from exc

        self.device = "cpu"
        self._warmup()
        logger.info("Detector ready (backend=onnx, device=cpu)")

    def _resolve_device(self) -> str:
        try:
            import torch

            if settings.DEVICE == "cpu":
                return "cpu"
            if settings.DEVICE in ("auto", "cuda") and torch.cuda.is_available():
                return "cuda"
        except Exception as exc:  # pragma: no cover
            logger.warning("torch unavailable (%s); using CPU", exc)
        return "cpu"

    def _load_torch(self) -> None:
        self.device = self._resolve_device()
        from pathlib import Path

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "The 'torch' backend requires ultralytics + torch. Install them "
                "with `pip install -r requirements-torch.txt`, or switch to "
                "MODEL_BACKEND=onnx."
            ) from exc

        if not Path(settings.MODEL_PATH).exists():
            raise RuntimeError(
                f"Model weights not found at '{settings.MODEL_PATH}'. Place your "
                "yolov26s.pt there or set MODEL_PATH in your .env."
            )

        try:
            self.model = YOLO(settings.MODEL_PATH)
            self.model.to(self.device)
        except Exception as exc:
            raise RuntimeError(f"Failed to load .pt model: {exc}") from exc

        self._warmup()
        logger.info("Detector ready (backend=torch, device=%s)", self.device)

    def _warmup(self) -> None:
        dummy = np.zeros(
            (settings.MODEL_IMG_SIZE, settings.MODEL_IMG_SIZE, 3), dtype=np.uint8
        )
        try:
            self._predict_sync(dummy)
        except Exception:  # pragma: no cover
            pass

    # --------------------------------------------------------------- inference
    def _predict_sync(self, frame: np.ndarray) -> InferenceResult:
        if not self.is_ready:
            raise RuntimeError(
                self.load_error
                or "Model is not loaded; a real model is required for inference."
            )
        t0 = time.perf_counter()
        lb = letterbox(frame, settings.MODEL_IMG_SIZE)

        if self.backend == "onnx":
            result = self._predict_onnx(lb)
        else:
            result = self._predict_torch(lb)

        result.latency_ms = (time.perf_counter() - t0) * 1000.0
        result.device = self.device
        return result

    def _predict_onnx(self, lb) -> InferenceResult:
        detections: List[Detection] = []
        for cls_id, conf, box in self.onnx.infer(lb):
            name = (
                labels.CLASS_NAMES[cls_id]
                if 0 <= cls_id < len(labels.CLASS_NAMES)
                else str(cls_id)
            )
            detections.append(
                Detection(cls_id, name, labels.glyph_for(name), conf, box)
            )
        return InferenceResult(detections=detections)

    def _predict_torch(self, lb) -> InferenceResult:
        preds = self.model.predict(
            lb.image,
            imgsz=settings.MODEL_IMG_SIZE,
            conf=settings.CONF_THRESHOLD,
            iou=settings.IOU_THRESHOLD,
            half=settings.HALF_PRECISION and self.device == "cuda",
            device=self.device,
            verbose=False,
        )
        detections: List[Detection] = []
        r = preds[0]
        boxes = getattr(r, "boxes", None)
        if boxes is not None:
            for b in boxes:
                cls_id = int(b.cls[0])
                conf = float(b.conf[0])
                xyxy = tuple(float(v) for v in b.xyxy[0].tolist())
                box = scale_box_to_original(xyxy, lb)
                name = (
                    labels.CLASS_NAMES[cls_id]
                    if 0 <= cls_id < len(labels.CLASS_NAMES)
                    else str(cls_id)
                )
                detections.append(
                    Detection(cls_id, name, labels.glyph_for(name), conf, box)
                )
        return InferenceResult(detections=detections)

    async def predict(self, frame: np.ndarray) -> InferenceResult:
        return await asyncio.to_thread(self._predict_sync, frame)

    # ----------------------------------------------------------------- helpers
    @property
    def is_ready(self) -> bool:
        return self.onnx is not None or self.model is not None

    @property
    def info(self) -> dict:
        return {
            "backend": self.backend,
            "device": self.device,
            "loaded": self.is_ready,
            "error": self.load_error,
            "img_size": settings.MODEL_IMG_SIZE,
            "model_path": (
                settings.ONNX_MODEL_PATH if self.backend == "onnx" else settings.MODEL_PATH
            ),
            "classes": len(labels.CLASS_NAMES),
        }


def get_detector() -> SignDetector:
    return SignDetector.instance()
