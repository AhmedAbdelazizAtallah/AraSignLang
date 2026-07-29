"""
Stable prediction engine (v2 — tuned for slow CPU / video).

Turns noisy per-frame detections into smooth "typing". A letter is ACCEPTED
(added to the text) when it has been the dominant, confident detection for a few
consecutive analysed frames.

What changed vs v1 (fixes "letter detected but never added to text"):
  * Consecutive-streak logic instead of a fixed 8-frame window vote. On a slow
    CPU (e.g. Render) only a few frames are analysed while a sign is held, so a
    large window rarely filled up → nothing was ever accepted. Now only
    `STABILITY_MIN_VOTES` consecutive agreeing frames are needed (default 3).
  * Re-typing the SAME letter is allowed again after the letter is absent for a
    couple of frames (no need to fully clear the whole window).
  * Confidence is smoothed over the current streak so a single noisy frame
    doesn't block acceptance.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

from backend.config import labels
from backend.config.settings import settings


@dataclass
class StableOutput:
    smoothed_letter: Optional[str]
    smoothed_glyph: str
    smoothed_conf: float
    accepted: bool
    accepted_glyph: str
    accepted_name: str


class PredictionStabilizer:
    """Per-session temporal smoother + streak voter + cooldown gate."""

    def __init__(self) -> None:
        self._current: Optional[str] = None          # letter of the current streak
        self._streak: int = 0                         # consecutive agreeing frames
        self._streak_confs: Deque[float] = deque(maxlen=12)
        self._last_accepted: Optional[str] = None
        self._last_accept_time: float = 0.0
        self._absent_frames: int = 0                  # frames since we saw a real letter

    def reset(self) -> None:
        self._current = None
        self._streak = 0
        self._streak_confs.clear()
        self._last_accepted = None
        self._last_accept_time = 0.0
        self._absent_frames = 0

    def update(
        self, class_name: Optional[str], confidence: float, now: float | None = None
    ) -> StableOutput:
        now = time.monotonic() if now is None else now

        # ------------------------------------------------- no / weak detection
        if not class_name or confidence < settings.CONF_THRESHOLD:
            self._absent_frames += 1
            # After a short gap, allow the same letter to be typed again.
            if self._absent_frames >= settings.REPEAT_RESET_FRAMES:
                self._last_accepted = None
            # Decay the current streak so a brief dropout doesn't accept stale data.
            self._current = None
            self._streak = 0
            self._streak_confs.clear()
            return StableOutput(None, "", 0.0, False, "", "")

        self._absent_frames = 0

        # ------------------------------------------------- update the streak
        if class_name == self._current:
            self._streak += 1
        else:
            self._current = class_name
            self._streak = 1
            self._streak_confs.clear()
        self._streak_confs.append(confidence)

        smoothed_conf = sum(self._streak_confs) / len(self._streak_confs)
        glyph = labels.glyph_for(class_name)

        # ------------------------------------------------- acceptance decision
        accepted = False
        accepted_glyph = ""
        accepted_name = ""

        if (
            self._streak >= settings.STABILITY_MIN_VOTES
            and smoothed_conf >= settings.ACCEPT_THRESHOLD
            and class_name != self._last_accepted
            and (now - self._last_accept_time) >= settings.COOLDOWN_SECONDS
        ):
            accepted = True
            accepted_name = class_name
            accepted_glyph = glyph
            self._last_accepted = class_name
            self._last_accept_time = now

        return StableOutput(
            smoothed_letter=class_name,
            smoothed_glyph=glyph,
            smoothed_conf=round(smoothed_conf, 4),
            accepted=accepted,
            accepted_glyph=accepted_glyph,
            accepted_name=accepted_name,
        )
