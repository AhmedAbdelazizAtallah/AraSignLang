"""Session analytics, history and export endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.models.schemas import ExportRequest
from backend.services import report_service
from backend.services.session_service import session_manager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/history")
async def history() -> dict:
    return {"sessions": session_manager.history()}


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    s = session_manager.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return s.as_dict()


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    ok = session_manager.delete_history(session_id)
    if not ok:
        raise HTTPException(404, "Session not found in history")
    return {"deleted": session_id}


@router.post("/export")
async def export_session(req: ExportRequest) -> FileResponse:
    stats = session_manager.get(req.session_id)
    data = stats.as_dict() if stats else None
    if data is None:
        for h in session_manager.history():
            if h["session_id"] == req.session_id:
                data = h
                break
    if data is None:
        raise HTTPException(404, "Session not found")

    try:
        path = report_service.export(data, req.format)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return FileResponse(path, filename=Path(path).name)
