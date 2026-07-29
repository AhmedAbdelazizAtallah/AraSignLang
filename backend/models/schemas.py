"""Pydantic request/response models shared across the API."""
from __future__ import annotations

from typing import List, Tuple

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    model: dict


class DetectionDTO(BaseModel):
    glyph: str
    name: str
    confidence: float
    box: Tuple[int, int, int, int]


class ImageResult(BaseModel):
    output_path: str
    download_name: str
    letter: str
    name: str
    confidence: float
    detections: List[DetectionDTO]
    latency_ms: float
    device: str


class TimelineDTO(BaseModel):
    frame_index: int
    timestamp_s: float
    glyph: str
    name: str
    confidence: float


class VideoResultDTO(BaseModel):
    job_id: str
    output_url: str
    frames: int
    fps: float
    duration_s: float
    generated_text: str
    avg_confidence: float
    device: str
    timeline: List[TimelineDTO]


class SuggestRequest(BaseModel):
    prefix: str
    limit: int = 6


class SuggestResponse(BaseModel):
    prefix: str
    words: List[str]


class SentenceRequest(BaseModel):
    text: str
    limit: int = 5


class SentenceResponse(BaseModel):
    sentences: List[str]


class ExportRequest(BaseModel):
    session_id: str
    format: str


class SessionDTO(BaseModel):
    session_id: str
    duration_s: float
    frames_processed: int
    avg_confidence: float
    generated_text: str
    device: str
