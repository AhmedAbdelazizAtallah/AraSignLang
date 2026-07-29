"""Health-check & model info endpoints (used by Docker/Render probes)."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config.settings import settings
from backend.inference.detector import get_detector
from backend.models.schemas import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    detector = get_detector()
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        env=settings.APP_ENV,
        model=detector.info,
    )
