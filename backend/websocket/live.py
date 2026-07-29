"""
Real-time live-camera WebSocket endpoint.

Browser sends { "type": "frame", "data": "<base64 jpeg>" } and the server
replies with a prediction payload per frame. Control messages: "reset", "text",
"end". If no real model is loaded, the socket rejects with a clear error — no
fake predictions.
"""
from __future__ import annotations

import base64
import time

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.config.settings import settings
from backend.inference.detector import get_detector
from backend.inference.stabilizer import PredictionStabilizer
from backend.services.session_service import session_manager
from backend.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _decode_frame(data_url: str) -> np.ndarray | None:
    try:
        if "," in data_url:
            data_url = data_url.split(",", 1)[1]
        raw = base64.b64decode(data_url)
        arr = np.frombuffer(raw, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _assess_quality(frame: np.ndarray, best) -> tuple[str, str, str]:
    h, w = frame.shape[:2]
    brightness = float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))

    if best is None:
        quality = "low_light" if brightness < 55 else "none"
        guide = "out"
        hint = "Improve Lighting" if brightness < 55 else "No hand detected"
        return quality, guide, hint

    side = min(h, w, settings.MODEL_IMG_SIZE)
    gx0, gy0 = (w - side) // 2, (h - side) // 2
    gx1, gy1 = gx0 + side, gy0 + side
    x1, y1, x2, y2 = best.box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    box_area = max(1, (x2 - x1) * (y2 - y1))
    guide_area = side * side

    inside = gx0 <= cx <= gx1 and gy0 <= cy <= gy1
    if not inside:
        hint = "Move Left" if cx > gx1 else "Move Right"
        return "partial", "adjust", hint

    ratio = box_area / guide_area
    if ratio < 0.15:
        return "ok", "adjust", "Move Closer"
    if ratio > 0.85:
        return "ok", "adjust", "Move Farther"
    if brightness < 55:
        return "low_light", "adjust", "Improve Lighting"
    return "ok", "ok", "Perfect"


@router.websocket("/ws/live")
async def live_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    detector = get_detector()

    if not detector.is_ready:
        await websocket.send_json(
            {"type": "error", "message": detector.load_error or "Model not loaded."}
        )
        await websocket.close()
        return

    stabilizer = PredictionStabilizer()
    session = session_manager.create()
    last_time = time.perf_counter()

    await websocket.send_json(
        {"type": "session", "session_id": session.session_id, "device": detector.device}
    )
    logger.info("Live session %s started (device=%s)", session.session_id, detector.device)

    try:
        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")

            if mtype == "reset":
                stabilizer.reset()
                await websocket.send_json({"type": "reset_ok"})
                continue

            if mtype == "text":
                session_manager.set_text(session.session_id, msg.get("value", ""))
                continue

            if mtype == "end":
                stats = session_manager.end(session.session_id)
                await websocket.send_json(
                    {"type": "ended", "stats": stats.as_dict() if stats else {}}
                )
                break

            if mtype != "frame":
                continue

            frame = _decode_frame(msg.get("data", ""))
            if frame is None:
                continue

            result = await detector.predict(frame)
            best = result.best

            stable = stabilizer.update(
                best.class_name if best else None,
                best.confidence if best else 0.0,
            )

            now = time.perf_counter()
            fps = 1.0 / max(1e-6, now - last_time)
            last_time = now

            quality, guide, hint = _assess_quality(frame, best)

            session_manager.record_frame(
                session.session_id,
                confidence=best.confidence if best else 0.0,
                latency_ms=result.latency_ms,
                fps=fps,
                device=result.device,
                raw_letter=best.class_name if best else None,
            )
            if stable.accepted:
                session_manager.record_accepted(
                    session.session_id, stable.accepted_glyph, stable.accepted_name
                )

            await websocket.send_json(
                {
                    "type": "prediction",
                    "best": (
                        {
                            "glyph": best.glyph,
                            "name": best.class_name,
                            "confidence": round(best.confidence, 4),
                            "box": list(best.box),
                        }
                        if best
                        else None
                    ),
                    "stable": {
                        "smoothed_glyph": stable.smoothed_glyph,
                        "smoothed_conf": stable.smoothed_conf,
                        "accepted": stable.accepted,
                        "accepted_glyph": stable.accepted_glyph,
                        "accepted_name": stable.accepted_name,
                    },
                    "quality": quality,
                    "guide": guide,
                    "hint": hint,
                    "stats": {
                        "fps": round(fps, 1),
                        "latency_ms": round(result.latency_ms, 1),
                        "device": result.device,
                        "frames": session.frames_processed,
                    },
                }
            )
    except WebSocketDisconnect:
        session_manager.end(session.session_id)
        logger.info("Live session %s disconnected", session.session_id)
    except Exception:  # pragma: no cover
        logger.exception("Live websocket error")
        session_manager.end(session.session_id)


