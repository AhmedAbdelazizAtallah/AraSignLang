"""
Application configuration.

All runtime configuration is centralised here and driven by environment
variables (loaded from a `.env` file when present).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Strongly-typed, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ----------------------------------------------------------------- app
    APP_NAME: str = "Arabic Sign Language AI"
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str = "change-me-in-production"

    # -------------------------------------------------------------- model
    MODEL_BACKEND: str = "onnx"        # onnx | torch
    ONNX_MODEL_PATH: str = str(BASE_DIR / "backend" / "models" / "yolov26s.onnx")
    MODEL_PATH: str = str(BASE_DIR / "backend" / "models" / "yolov26s.pt")
    MODEL_IMG_SIZE: int = 416          # the ONLY resolution the model was trained on
    DEVICE: str = "auto"               # auto | cuda | cpu (torch backend only)
    HALF_PRECISION: bool = True

    # letterbox (safest, no crop) | center_crop (hand must be centred)
    PREPROCESS_MODE: str = "letterbox"

    # ------------------------------------------------------ inference / stability
    CONF_THRESHOLD: float = 0.45       # min confidence to consider a detection
    IOU_THRESHOLD: float = 0.45
    # Consecutive agreeing frames needed to ACCEPT (type) a letter. Kept small so
    # it works even on slow CPUs (Render) where few frames are analysed per sign.
    STABILITY_MIN_VOTES: int = 3
    STABILITY_WINDOW: int = 8          # kept for backward-compat (unused in v2)
    ACCEPT_THRESHOLD: float = 0.60     # confidence needed to *type* a letter
    COOLDOWN_SECONDS: float = 0.8      # min time between two accepted letters
    # Frames of "no/low detection" after which the SAME letter can be typed again.
    REPEAT_RESET_FRAMES: int = 3
    MAX_HISTORY: int = 200

    # ---------------------------------------------------------------- uploads
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "outputs"
    REPORT_DIR: Path = BASE_DIR / "reports"
    MAX_UPLOAD_MB: int = 200
    ALLOWED_VIDEO_EXT: List[str] = [".mp4", ".mov", ".avi", ".mkv"]
    ALLOWED_IMAGE_EXT: List[str] = [".jpg", ".jpeg", ".png", ".webp"]

    # ------------------------------------------------------------------- cors
    CORS_ORIGINS: List[str] = ["*"]

    # ---------------------------------------------------------------- logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = BASE_DIR / "backend" / "reports" / "logs"

    def ensure_dirs(self) -> None:
        for d in (self.UPLOAD_DIR, self.OUTPUT_DIR, self.REPORT_DIR, self.LOG_DIR):
            Path(d).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()
