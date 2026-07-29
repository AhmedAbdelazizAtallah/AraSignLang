"""
Image & video upload / analysis endpoints.

Video analysis runs as a BACKGROUND task: the upload endpoint returns a job_id
immediately, and the browser polls /api/video/progress/{job_id} for progress and
the final result. This prevents the request from hanging while a long video is
processed on CPU.
"""
from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.config.settings import settings
from backend.inference.detector import get_detector
from backend.models.schemas import ImageResult
from backend.services import media_service
from backend.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])

# In-memory job registry: job_id -> {status, progress, result, error}
VIDEO_JOBS: dict[str, dict] = {}


def _save_upload(file: UploadFile, allowed: list[str]) -> Path:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {allowed}")
    dest = settings.UPLOAD_DIR / f"{uuid.uuid4().hex[:10]}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    size_mb = dest.stat().st_size / 1_000_000
    if size_mb > settings.MAX_UPLOAD_MB:
        dest.unlink(missing_ok=True)
        raise HTTPException(413, f"File too large ({size_mb:.1f} MB).")
    return dest


def _ensure_model():
    det = get_detector()
    if not det.is_ready:
        raise HTTPException(503, det.load_error or "Model not loaded.")
    return det


@router.post("/detect/image", response_model=ImageResult)
async def detect_image(file: UploadFile = File(...)) -> ImageResult:
    det = _ensure_model()
    path = _save_upload(file, settings.ALLOWED_IMAGE_EXT)
    try:
        result = await media_service.analyse_image(path, det)
        return ImageResult(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Image analysis failed")
        raise HTTPException(500, str(exc))


async def _run_video_job(job_id: str, path: Path) -> None:
    """Background worker: processes the video and updates the job registry."""
    det = get_detector()
    job = VIDEO_JOBS[job_id]
    job["status"] = "processing"

    def _progress(p: float) -> None:
        job["progress"] = round(p, 4)

    try:
        result = await media_service.analyse_video(path, det, _progress)
        job.update(
            status="done",
            progress=1.0,
            result={
                "job_id": job_id,
                "output_url": f"/api/download/video/{job_id}",
                "frames": result.frames,
                "fps": result.fps,
                "duration_s": result.duration_s,
                "generated_text": result.generated_text,
                "avg_confidence": result.avg_confidence,
                "device": result.device,
                "timeline": [t.__dict__ for t in result.timeline],
            },
            output_path=result.output_path,
        )
        logger.info("Video job %s done (%d frames)", job_id, result.frames)
    except Exception as exc:  # pragma: no cover
        logger.exception("Video job %s failed", job_id)
        job.update(status="error", error=str(exc))


@router.post("/detect/video")
async def detect_video(file: UploadFile = File(...)) -> dict:
    """Start a background video-analysis job and return its id immediately."""
    _ensure_model()
    path = _save_upload(file, settings.ALLOWED_VIDEO_EXT)
    job_id = uuid.uuid4().hex[:10]
    VIDEO_JOBS[job_id] = {"status": "queued", "progress": 0.0, "result": None, "error": None}
    # Fire-and-forget background task (runs in the same event loop).
    asyncio.create_task(_run_video_job(job_id, path))
    return {"job_id": job_id, "status": "queued"}


@router.get("/video/progress/{job_id}")
async def video_progress(job_id: str) -> dict:
    """Poll job status/progress and, when finished, the full result."""
    job = VIDEO_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "result": job["result"],
        "error": job["error"],
    }


@router.get("/download/video/{job_id}")
async def download_video(job_id: str) -> FileResponse:
    job = VIDEO_JOBS.get(job_id)
    path = job.get("output_path") if job else None
    if not path or not Path(path).exists():
        raise HTTPException(404, "Processed video not found")
    return FileResponse(path, media_type="video/mp4", filename=Path(path).name)


@router.get("/download/output/{name}")
async def download_output(name: str) -> FileResponse:
    path = settings.OUTPUT_DIR / name
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=name)
