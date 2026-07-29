"""
ONNX Runtime inference backend (lightweight, low-RAM) — supports BOTH:

  (A) End-to-end / NMS-embedded exports  → output shape [1, max_det, 6]
      Each row = [x1, y1, x2, y2, score, class_id]   (boxes already xyxy,
      already NMS-ed). This is what THIS project's model uses.

  (B) Raw YOLOv8/v11 detection heads       → output shape [1, 4+nc, N]
      or [1, N, 4+nc]  (cx,cy,w,h + per-class scores, needs NMS).

The backend auto-detects which format the model produced and decodes it
correctly. This fixes the two bugs seen with format (A):
  * "always the same letter (ب)"  — was caused by argmax over [score, class_id]
    instead of reading the class_id column directly.
  * "wrong / garbled box"         — was caused by treating x1,y1,x2,y2 as
    cx,cy,w,h.

Runs with onnxruntime only (no torch), so it stays light for free hosting.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

from backend.config import labels
from backend.config.settings import settings
from backend.inference.preprocessing import LetterBoxResult, scale_box_to_original
from backend.utils.logging import get_logger

logger = get_logger(__name__)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


class OnnxDetector:
    """Runs a YOLO detection ONNX model with format-aware post-processing."""

    def __init__(self, model_path: str) -> None:
        import onnxruntime as ort

        if not Path(model_path).exists():
            raise FileNotFoundError(model_path)

        providers = ["CPUExecutionProvider"]
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(model_path, sess_options=so, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.img_size = settings.MODEL_IMG_SIZE
        self.label_classes = len(labels.CLASS_NAMES)
        logger.info(
            "ONNX loaded: %s | output=%s | labels.py classes=%d",
            model_path, self.session.get_outputs()[0].shape, self.label_classes,
        )

    # ------------------------------------------------------------------ infer
    def infer(self, lb: LetterBoxResult) -> List[Tuple[int, float, tuple]]:
        img = cv2.cvtColor(lb.image, cv2.COLOR_BGR2RGB)
        tensor = img.transpose(2, 0, 1).astype(np.float32) / 255.0
        tensor = np.expand_dims(tensor, 0)
        outputs = self.session.run(self.output_names, {self.input_name: tensor})
        return self._postprocess(outputs[0], lb)

    # --------------------------------------------------------------- post-proc
    def _name_for(self, cls_id: int) -> str:
        if 0 <= cls_id < self.label_classes:
            return labels.CLASS_NAMES[cls_id]
        return str(cls_id)

    def _postprocess(self, preds: np.ndarray, lb: LetterBoxResult):
        p = np.squeeze(preds, 0) if preds.ndim == 3 else preds
        if p.ndim != 2:
            return []

        # Orient to (num_rows, features): rows (detections/anchors) is the
        # larger axis for the raw head; for end-to-end it's already (max_det, 6).
        if p.shape[0] < p.shape[1]:
            p = p.transpose()
        feat = p.shape[1]

        # -------- Format (A): end-to-end / NMS-embedded → [x1,y1,x2,y2,score,cls]
        if feat == 6:
            return self._decode_end_to_end(p, lb)

        # -------- Format (B): raw YOLO head (4+nc) or (5+nc) --------------------
        return self._decode_raw_yolo(p, lb)

    def _decode_end_to_end(self, p: np.ndarray, lb: LetterBoxResult):
        """Decode [x1, y1, x2, y2, score, class_id] rows (already NMS-ed)."""
        boxes = p[:, :4].astype(np.float32)      # xyxy in 416 letterbox space
        scores = p[:, 4].astype(np.float32)
        class_ids = np.rint(p[:, 5]).astype(int)  # class id stored as float

        keep = scores >= settings.CONF_THRESHOLD
        boxes, scores, class_ids = boxes[keep], scores[keep], class_ids[keep]
        if boxes.shape[0] == 0:
            return []

        # If boxes look normalised (0..1), scale to the 416 canvas.
        if float(np.max(np.abs(boxes))) <= 1.5:
            boxes = boxes * self.img_size

        # Keep only the single best detection (one letter at a time).
        order = np.argsort(scores)[::-1]
        best = order[0]
        box_orig = scale_box_to_original(tuple(boxes[best]), lb)
        return [(int(class_ids[best]), float(scores[best]), box_orig)]

    def _decode_raw_yolo(self, p: np.ndarray, lb: LetterBoxResult):
        """Decode a raw YOLO head: cx,cy,w,h + per-class scores → NMS → best."""
        feat = p.shape[1]
        nc = feat - 4  # assume YOLOv8/v11 layout [x,y,w,h, c0..c(nc-1)]
        box = p[:, :4].astype(np.float32)
        cls = p[:, 4:4 + nc].astype(np.float32)
        if cls.size and cls.max() > 1.0:  # raw logits → probabilities
            cls = _sigmoid(cls)
        if cls.size == 0:
            return []

        class_ids = np.argmax(cls, axis=1)
        confidences = cls[np.arange(cls.shape[0]), class_ids]

        keep = confidences >= settings.CONF_THRESHOLD
        box, confidences, class_ids = box[keep], confidences[keep], class_ids[keep]
        if box.shape[0] == 0:
            return []

        if float(np.max(box)) <= 1.5:
            box = box * self.img_size

        cx, cy, w, h = box.T
        x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        idxs = cv2.dnn.NMSBoxes(
            bboxes=[[float(a), float(b), float(c - a), float(d - b)] for a, b, c, d in boxes_xyxy],
            scores=confidences.tolist(),
            score_threshold=settings.CONF_THRESHOLD,
            nms_threshold=settings.IOU_THRESHOLD,
        )
        if len(idxs) == 0:
            return []
        idxs = np.array(idxs).flatten()

        best = max(idxs, key=lambda i: confidences[i])
        box_orig = scale_box_to_original(tuple(boxes_xyxy[best]), lb)
        return [(int(class_ids[best]), float(confidences[best]), box_orig)]
