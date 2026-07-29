"""Centralised structured logging configuration."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from backend.config.settings import settings

_CONFIGURED = False
_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings.ensure_dirs()
    root = logging.getLogger()
    level = logging.getLevelName(str(settings.LOG_LEVEL).strip().upper())
    root.setLevel(level if isinstance(level, int) else logging.INFO)

    formatter = logging.Formatter(_FMT, datefmt="%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        file_handler = RotatingFileHandler(
            settings.LOG_DIR / "app.log", maxBytes=5_000_000, backupCount=3
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except Exception:
        pass

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(name)
