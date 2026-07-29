"""
Image & video analysis services.

Both share the *exact same* inference pipeline as live mode (LetterBox 416 ->
detector -> stabilizer) so results are consistent across all three input modes.

* `analyse_image`  : single-frame detection -> annotated image on disk.
* `analyse_video`  : frame reader (with configurable frame-sampling to stay fast
                     on CPU) + async inference -> annotated MP4 with overlays, a
                     per-frame timeline and full stats. Reports progress via a
                     callback so the API can stream it to the browser.

NOTE: the model recognises ONE letter at a time, so we draw ONLY the best
(highest-confidence) detection — never the full list of raw candidate boxes.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import cv2

from backend.config.settings import settings
from backend.inference.detector import SignDetector
from backend.inference.stabilizer import PredictionStabilizer
from backend.utils.draw import draw_detection
from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Analyse at most this many frames per second of video. On CPU, running every
# single frame of a 30 fps clip is very slow, so we sample. Sign letters are
# held for a while, so sampling keeps accuracy while being much faster.
TARGET_ANALYSIS_FPS = 6


@dataclass
class TimelineEntry:
    frame_index: int
    timestamp_s: float
    glyph: str
    name: str
    confidence: float


@dataclass
class VideoResult:
    output_path: str
    frames: int
    fps: float
    duration_s: float
    generated_text: str
    timeline: List[TimelineEntry] = field(default_factory=list)
    avg_confidence: float = 0.0
    device: str = "cpu"


async def analyse_image(src_path: Path, detector: SignDetector) -> Dict:
    """Run detection on a single image and save an annotated copy."""
    image = cv2.imread(str(src_path))
    if image is None:
        raise ValueError("Could not read image file")

    result = await detector.predict(image)
    best = result.best

    if best:
        image = draw_detection(image, best.glyph, best.confidence, best.box)

    out_path = settings.OUTPUT_DIR / f"annotated_{src_path.stem}.png"
    cv2.imwrite(str(out_path), image)

    return {
        "output_path": str(out_path),
        "download_name": out_path.name,
        "letter": best.glyph if best else "",
        "name": best.class_name if best else "",
        "confidence": round(best.confidence, 4) if best else 0.0,
        "detections": (
            [{
                "glyph": best.glyph, "name": best.class_name,
                "confidence": round(best.confidence, 4), "box": best.box,
            }] if best else []
        ),
        "latency_ms": round(result.latency_ms, 2),
        "device": result.device,
    }


async def analyse_video(
    src_path: Path,
    detector: SignDetector,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> VideoResult:
    """Analyse a video with frame-sampling and the shared inference pipeline.

    `progress_cb(fraction)` is called regularly (0..1) so callers can report
    progress to the browser.
    """
    cap = cv2.VideoCapture(str(src_path))
    if not cap.isOpened():
        raise ValueError("Could not open video file")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    # Sample every Nth frame to hit ~TARGET_ANALYSIS_FPS.
    step = max(1, int(round(fps / TARGET_ANALYSIS_FPS)))

    out_path = settings.OUTPUT_DIR / f"processed_{src_path.stem}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    # Write the output at the (lower) analysis fps so the file stays small.
    out_fps = max(1.0, fps / step)
    writer = cv2.VideoWriter(str(out_path), fourcc, out_fps, (width, height))

    stabilizer = PredictionStabilizer()
    stabilizer.reset()

    timeline: List[TimelineEntry] = []
    text_parts: List[str] = []
    confidences: List[float] = []

    idx = 0
    analysed = 0
    if progress_cb:
        progress_cb(0.0)

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        # Skip frames that aren't on the sampling grid.
        if idx % step != 0:
            idx += 1
            continue

        result = await detector.predict(frame)
        best = result.best

        if best:
            frame = draw_detection(frame, best.glyph, best.confidence, best.box)
            confidences.append(best.confidence)

        stable = stabilizer.update(
            best.class_name if best else None,
            best.confidence if best else 0.0,
        )
        if stable.accepted:
            ts = idx / fps
            timeline.append(TimelineEntry(
                frame_index=idx, timestamp_s=round(ts, 3),
                glyph=stable.accepted_glyph, name=stable.accepted_name,
                confidence=stable.smoothed_conf,
            ))
            text_parts.append(stable.accepted_glyph)

        writer.write(frame)
        analysed += 1
        idx += 1

        if progress_cb and total:
            progress_cb(min(0.99, idx / total))
        # Yield to the event loop so the server stays responsive.
        await asyncio.sleep(0)

    cap.release()
    writer.release()
    if progress_cb:
        progress_cb(1.0)

    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
    return VideoResult(
        output_path=str(out_path),
        frames=analysed,
        fps=round(out_fps, 2),
        duration_s=round(total / fps, 2) if fps else 0.0,
        generated_text="".join(text_parts),
        timeline=timeline,
        avg_confidence=avg_conf,
        device=detector.device,
    )
