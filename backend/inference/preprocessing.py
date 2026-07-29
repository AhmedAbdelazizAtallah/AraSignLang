"""
Frame pre-processing utilities.

The model was trained ONLY on 416x416 images, so every incoming frame is
converted to 416x416 before inference — identically for live camera, video and
image, so predictions are consistent everywhere.

Two modes (see `PREPROCESS_MODE` in settings/.env):

  * "letterbox" (default, safest): resize preserving aspect ratio and pad with
    grey to a 416 square. NOTHING is cropped, so the hand is never accidentally
    cut off — ideal for the live camera where the hand may not be dead-centre.

  * "center_crop": crop the largest CENTERED square then resize to 416. Keeps
    the hand larger (good for wide videos) but the hand MUST be near the centre.

Both keep the transform parameters so detected boxes map back to original-frame
coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from backend.config.settings import settings


@dataclass
class Transform:
    """A preprocessed 416 image plus the info needed to invert the transform."""

    image: np.ndarray
    ratio: float
    pad_x: float = 0.0
    pad_y: float = 0.0
    crop_x0: int = 0
    crop_y0: int = 0


# Backwards-compatible alias (older modules import LetterBoxResult).
LetterBoxResult = Transform


def letterbox(
    image: np.ndarray,
    new_size: int = 416,
    color: tuple[int, int, int] = (114, 114, 114),
) -> Transform:
    """Resize preserving aspect ratio and pad to a `new_size` square."""
    h, w = image.shape[:2]
    ratio = min(new_size / h, new_size / w)
    new_w, new_h = int(round(w * ratio)), int(round(h * ratio))

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_w = (new_size - new_w) / 2
    pad_h = (new_size - new_h) / 2
    top, bottom = int(round(pad_h - 0.1)), int(round(pad_h + 0.1))
    left, right = int(round(pad_w - 0.1)), int(round(pad_w + 0.1))

    padded = cv2.copyMakeBorder(
        resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color
    )
    return Transform(image=padded, ratio=ratio, pad_x=pad_w, pad_y=pad_h)


def center_crop_resize(image: np.ndarray, new_size: int = 416) -> Transform:
    """Crop the largest centered square, then resize to `new_size` square."""
    h, w = image.shape[:2]
    side = min(h, w)
    x0 = (w - side) // 2
    y0 = (h - side) // 2
    crop = image[y0:y0 + side, x0:x0 + side]
    resized = cv2.resize(crop, (new_size, new_size), interpolation=cv2.INTER_LINEAR)
    return Transform(image=resized, ratio=new_size / side, crop_x0=x0, crop_y0=y0)


def preprocess(image: np.ndarray, new_size: int = 416, mode: str | None = None) -> Transform:
    """Preprocess a frame using the configured mode (letterbox | center_crop)."""
    mode = (mode or getattr(settings, "PREPROCESS_MODE", "letterbox")).lower()
    if mode == "center_crop":
        return center_crop_resize(image, new_size)
    return letterbox(image, new_size)


def scale_box_to_original(
    box_xyxy: tuple[float, float, float, float],
    t: Transform,
) -> tuple[int, int, int, int]:
    """Map a box from 416-space back to the ORIGINAL frame (handles crop+pad)."""
    x1, y1, x2, y2 = box_xyxy
    x1 = (x1 - t.pad_x) / t.ratio + t.crop_x0
    x2 = (x2 - t.pad_x) / t.ratio + t.crop_x0
    y1 = (y1 - t.pad_y) / t.ratio + t.crop_y0
    y2 = (y2 - t.pad_y) / t.ratio + t.crop_y0
    return int(x1), int(y1), int(x2), int(y2)
