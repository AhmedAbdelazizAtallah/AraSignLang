"""
Arabic Sign Language AI — FastAPI application entrypoint.

Wires config, middleware, REST routers, the live-inference WebSocket, static
assets and the SPA template. The detection model (ONNX by default) loads lazily
and warms up at startup. Honours the platform-provided $PORT.

Local:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.api import detect, health, language, sessions
from backend.config.settings import settings
from backend.inference.detector import get_detector
from backend.middleware.setup import register_middleware
from backend.utils.logging import get_logger
from backend.websocket import live

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    detector = get_detector()
    if detector.is_ready:
        logger.info("Startup complete. Model info: %s", detector.info)
    else:
        logger.error(
            "⚠️  MODEL NOT LOADED — inference will be rejected until a real "
            "model is provided. Reason: %s",
            detector.load_error,
        )
    yield
    logger.info("Shutting down Arabic Sign Language AI.")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.2.0",
    description="Production-ready Arabic Sign Language Recognition (YOLOv26s / ONNX).",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

register_middleware(app)

app.include_router(health.router)
app.include_router(detect.router)
app.include_router(language.router)
app.include_router(sessions.router)
app.include_router(live.router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def index(request: Request) -> HTMLResponse:
    context = {"app_name": settings.APP_NAME, "img_size": settings.MODEL_IMG_SIZE}
    try:
        return templates.TemplateResponse(request, "index.html", context)
    except TypeError:
        return templates.TemplateResponse("index.html", {"request": request, **context})


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", settings.PORT))
    uvicorn.run("backend.main:app", host=settings.HOST, port=port, reload=settings.DEBUG)
