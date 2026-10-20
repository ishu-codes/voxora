"""Voxora API — FastAPI application entry point.

Owns the real-time voice WebSocket, provider selection and latency metrics.
No model code lives here: every stage is an adapter behind
``src.voice.providers``.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.voice.config import settings
from src.voice.rate_limit import StrictRateLimiter
from src.voice.router import ProviderBundle, shutdown_providers
from src.voice.router import router as voice_router

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("voxora")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.voice_providers = ProviderBundle.build(settings)
    app.state.rate_limiter = StrictRateLimiter(settings)
    bundle: ProviderBundle = app.state.voice_providers
    logger.info(
        "providers stt=sarvam:%s tts=sarvam:%s llm=%s (%s)",
        settings.stt_model,
        settings.tts_model,
        bundle.llm.name,
        bundle.reasons.get("llm"),
    )
    yield
    await shutdown_providers(app)


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exception: HTTPException):
    return JSONResponse(
        status_code=exception.status_code,
        content={"detail": exception.detail},
        headers=exception.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exception: Exception):
    logger.exception("Unhandled request error")
    return JSONResponse(status_code=500, content={"detail": str(exception)})


@app.get("/")
async def read_root() -> dict:
    return {
        "name": settings.app_name.lower(),
        "version": settings.version,
        "tagline": "From speech to intelligence and back, in real time.",
        "websocket": "/api/v1/voice/ws",
    }


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


app.include_router(voice_router, prefix="/api/v1/voice", tags=["Voice"])
