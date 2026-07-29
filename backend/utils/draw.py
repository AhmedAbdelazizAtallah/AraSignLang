"""
Overlay drawing helpers.

Renders modern, confidence-coloured bounding boxes and Arabic labels onto
frames. Arabic text is drawn with Pillow (OpenCV cannot render Arabic glyphs),
with automatic reshaping + bidi ordering so letters connect and render RTL.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

COLOR_HIGH = (80, 220, 120)
COLOR_MED = (60, 200, 240)
COLOR_LOW = (80, 90, 240)

_FONT_PATH = Path(__file__).resolve().parents[2] / "frontend" / "fonts" / "arabic.ttf"


def color_for_conf(conf: float) -> Tuple[int, int, int]:
    if conf >= 0.85:
        return COLOR_HIGH
    if conf >= 0.65:
        return COLOR_MED
    return COLOR_LOW


def _put_arabic(img: np.ndarray, text: str, org, color, size: int = 28) -> np.ndarray:
    try:
        from PIL import Image, ImageDraw, ImageFont
        import arabic_reshaper
        from bidi.algorithm import get_display

        reshaped = get_display(arabic_reshaper.reshape(text))
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)
        font = (
            ImageFont.truetype(str(_FONT_PATH), size)
            if _FONT_PATH.exists()
            else ImageFont.load_default()
        )
        rgb = (color[2], color[1], color[0])
        draw.text(org, reshaped, font=font, fill=rgb)
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    except Exception:
        cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
        return img


def draw_detection(
    frame: np.ndarray, glyph: str, conf: float, box: Tuple[int, int, int, int]
) -> np.ndarray:
    x1, y1, x2, y2 = box
    color = color_for_conf(conf)

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
    cv2.rectangle(frame, (x1 - 1, y1 - 1), (x2 + 1, y2 + 1), color, 1, cv2.LINE_AA)

    label = f"حرف : {glyph}"
    conf_label = f"{conf * 100:.1f}%"

    chip_h = 40
    cv2.rectangle(frame, (x1, max(0, y1 - chip_h)), (x1 + 190, y1), color, -1)
    frame = _put_arabic(frame, label, (x1 + 8, max(0, y1 - chip_h) + 4), (20, 20, 20), 26)
    cv2.putText(
        frame, conf_label, (x1 + 120, y1 - 12),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 2, cv2.LINE_AA,
    )
    return frame


def draw_guide(frame: np.ndarray, size: int = 416, status: str = "ok") -> np.ndarray:
    h, w = frame.shape[:2]
    side = min(h, w, size)
    x0 = (w - side) // 2
    y0 = (h - side) // 2
    colors = {"ok": COLOR_HIGH, "adjust": COLOR_MED, "out": COLOR_LOW}
    color = colors.get(status, COLOR_MED)
    cv2.rectangle(frame, (x0, y0), (x0 + side, y0 + side), color, 2, cv2.LINE_AA)
    return frame
