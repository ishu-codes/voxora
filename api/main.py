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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.voice.catalog import load_catalog
from src.voice.controller import router as voice_router
from src.voice.core.config import settings
from src.voice.providers import WHISPER_MODEL
from src.voice.security.rate_limit import StrictRateLimiter
from src.voice.services.provider_bundle import ProviderBundle, shutdown_providers

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("voxora")


@asynccontextmanager
async def lifespan(app: FastAPI):
    catalog = load_catalog()
    models = catalog["models"]
    logger.info(
        "voice catalog loaded models=%s voices=%d",
        ", ".join(models),
        sum(len(model["voices"]) for model in models.values()),
    )
    app.state.voice_providers = await ProviderBundle.initialize(settings)
    app.state.rate_limiter = StrictRateLimiter(settings)
    bundle: ProviderBundle = app.state.voice_providers
    logger.info(
        "providers stt=%s:%s tts=sarvam:%s llm=%s (%s)",
        settings.stt_provider,
        (
            settings.gnani_stt_model
            if settings.stt_provider == "gnani"
            else settings.stt_model
            if settings.stt_provider == "sarvam"
            else WHISPER_MODEL
        ),
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
