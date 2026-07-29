"""
Auto-complete API — Arabic word suggestions from a letter prefix.

Endpoint:
    GET /api/suggest?prefix=<letters>&limit=<n>

Returns:
    { "prefix": "...", "suggestions": ["باب", "بابا", ...] }

Register it in backend/main.py:
    from backend.api import suggest as suggest_api
    app.include_router(suggest_api.router)
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.services import arabic_dictionary as ad

router = APIRouter(prefix="/api", tags=["suggest"])


@router.get("/suggest")
async def suggest(
    prefix: str = Query("", description="Arabic letters typed so far"),
    limit: int = Query(6, ge=1, le=20),
) -> dict:
    """Return Arabic word suggestions for the given prefix."""
    suggestions = ad.suggest(prefix, limit=limit)
    return {"prefix": prefix, "suggestions": suggestions}
