"""
Stable prediction engine.

Raw per-frame detections are noisy. To produce smooth "typing" we only accept a
letter when it is: (1) stable across several frames (majority voting),
(2) above the accept confidence threshold, (3) different from the previously
accepted letter, and (4) outside the cooldown window.

Each session owns its own stabilizer so state never leaks between users.
"""
from __future__ import annotations

import time
from collections import Counter, deque
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
    """Per-session temporal smoother + majority voter + cooldown gate."""

    def __init__(self) -> None:
        self._window: Deque[str] = deque(maxlen=settings.STABILITY_WINDOW)
        self._conf_window: Deque[float] = deque(maxlen=settings.STABILITY_WINDOW)
        self._last_accepted: Optional[str] = None
        self._last_accept_time: float = 0.0

    def reset(self) -> None:
        self._window.clear()
        self._conf_window.clear()
        self._last_accepted = None
        self._last_accept_time = 0.0

    def update(
        self, class_name: Optional[str], confidence: float, now: float | None = None
    ) -> StableOutput:
        now = time.monotonic() if now is None else now

        # "__none__" is an internal placeholder for "no detection this frame".
        token = class_name or "__none__"
        self._window.append(token)
        self._conf_window.append(confidence if class_name else 0.0)

        votes = Counter(t for t in self._window if t != "__none__")
        smoothed_letter: Optional[str] = None
        smoothed_conf = 0.0
        if votes:
            smoothed_letter, count = votes.most_common(1)[0]
            matched = [
                c for t, c in zip(self._window, self._conf_window)
                if t == smoothed_letter
            ]
            smoothed_conf = sum(matched) / len(matched) if matched else 0.0
            has_majority = count >= settings.STABILITY_MIN_VOTES
        else:
            has_majority = False

        accepted = False
        accepted_glyph = ""
        accepted_name = ""

        if (
            has_majority
            and smoothed_letter is not None
            and smoothed_conf >= settings.ACCEPT_THRESHOLD
            and smoothed_letter != self._last_accepted
            and (now - self._last_accept_time) >= settings.COOLDOWN_SECONDS
        ):
            accepted = True
            accepted_name = smoothed_letter
            accepted_glyph = labels.glyph_for(smoothed_letter)
            self._last_accepted = smoothed_letter
            self._last_accept_time = now

        # A full window of "no detection" resets last_accepted so the same
        # letter can be typed again after lowering the hand.
        if token == "__none__" and self._window.count("__none__") >= len(self._window):
            self._last_accepted = None

        return StableOutput(
            smoothed_letter=smoothed_letter,
            smoothed_glyph=labels.glyph_for(smoothed_letter) if smoothed_letter else "",
            smoothed_conf=round(smoothed_conf, 4),
            accepted=accepted,
            accepted_glyph=accepted_glyph,
            accepted_name=accepted_name,
        )
