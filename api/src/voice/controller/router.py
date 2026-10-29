"""HTTP and WebSocket endpoints for the Voxora voice service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, WebSocket

from ..services.voice import (
    get_catalog,
    get_config,
    get_metrics,
    reset_metrics,
    serve_voice_socket,
)

router = APIRouter()


@router.get("/config")
async def voice_config(request: Request) -> dict[str, Any]:
    return get_config(request.app.state)


@router.get("/voices")
async def voice_catalog(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = (
        "public, max-age=86400, stale-while-revalidate=604800"
    )
    return get_catalog()


@router.get("/metrics")
async def voice_metrics() -> dict[str, Any]:
    return get_metrics()


@router.delete("/metrics")
async def reset_voice_metrics() -> dict[str, str]:
    return reset_metrics()


@router.websocket("/ws")
async def voice_socket(websocket: WebSocket) -> None:
    await serve_voice_socket(websocket)


__all__ = ["router"]
