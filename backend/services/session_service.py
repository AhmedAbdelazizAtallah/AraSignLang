"""
Session tracking & analytics.

Keeps in-memory statistics for each active recognition session and a rolling
history of finished sessions. Storage-agnostic so swapping to Redis/Postgres is
trivial.
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional


@dataclass
class SessionStats:
    session_id: str
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None

    frames_processed: int = 0
    total_latency_ms: float = 0.0
    confidences: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    fps_samples: Deque[float] = field(default_factory=lambda: deque(maxlen=120))

    detected_letters: List[str] = field(default_factory=list)
    accepted_letters: List[str] = field(default_factory=list)
    generated_text: str = ""
    device: str = "cpu"

    @property
    def duration_s(self) -> float:
        end = self.ended_at or time.time()
        return round(end - self.started_at, 2)

    @property
    def avg_confidence(self) -> float:
        return round(sum(self.confidences) / len(self.confidences), 4) if self.confidences else 0.0

    @property
    def max_confidence(self) -> float:
        return round(max(self.confidences), 4) if self.confidences else 0.0

    @property
    def min_confidence(self) -> float:
        return round(min(self.confidences), 4) if self.confidences else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return round(self.total_latency_ms / self.frames_processed, 2) if self.frames_processed else 0.0

    @property
    def avg_fps(self) -> float:
        return round(sum(self.fps_samples) / len(self.fps_samples), 2) if self.fps_samples else 0.0

    def as_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_s": self.duration_s,
            "frames_processed": self.frames_processed,
            "avg_confidence": self.avg_confidence,
            "max_confidence": self.max_confidence,
            "min_confidence": self.min_confidence,
            "avg_latency_ms": self.avg_latency_ms,
            "avg_fps": self.avg_fps,
            "detected_letters": self.detected_letters,
            "accepted_letters": self.accepted_letters,
            "generated_text": self.generated_text,
            "device": self.device,
        }


class SessionManager:
    _instance: "SessionManager | None" = None

    def __init__(self) -> None:
        self._active: Dict[str, SessionStats] = {}
        self._history: Deque[SessionStats] = deque(maxlen=100)

    @classmethod
    def instance(cls) -> "SessionManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create(self) -> SessionStats:
        sid = uuid.uuid4().hex[:12]
        stats = SessionStats(session_id=sid)
        self._active[sid] = stats
        return stats

    def get(self, session_id: str) -> Optional[SessionStats]:
        return self._active.get(session_id)

    def record_frame(
        self, session_id: str, confidence: float, latency_ms: float,
        fps: float, device: str, raw_letter: Optional[str] = None,
    ) -> None:
        s = self._active.get(session_id)
        if not s:
            return
        s.frames_processed += 1
        s.total_latency_ms += latency_ms
        if confidence:
            s.confidences.append(confidence)
        if fps:
            s.fps_samples.append(fps)
        s.device = device
        if raw_letter:
            s.detected_letters.append(raw_letter)

    def record_accepted(self, session_id: str, glyph: str, name: str) -> None:
        s = self._active.get(session_id)
        if s:
            s.accepted_letters.append(name)

    def set_text(self, session_id: str, text: str) -> None:
        s = self._active.get(session_id)
        if s:
            s.generated_text = text

    def end(self, session_id: str) -> Optional[SessionStats]:
        s = self._active.pop(session_id, None)
        if s:
            s.ended_at = time.time()
            self._history.appendleft(s)
        return s

    def history(self) -> List[Dict]:
        return [s.as_dict() for s in self._history]

    def delete_history(self, session_id: str) -> bool:
        for s in list(self._history):
            if s.session_id == session_id:
                self._history.remove(s)
                return True
        return False


session_manager = SessionManager.instance()
