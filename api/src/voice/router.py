"""FastAPI routes for the Voxora real-time voice service."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from .config import Settings, settings
from .metrics import registry
from .pipeline import VoicePipeline
from .providers import build_llm, build_stt, build_tts
from .providers.base import LLMProvider, STTProvider, TTSProvider
from .transport import QueueTransport
from .vad import EnergyVAD

logger = logging.getLogger(__name__)

router = APIRouter()


@dataclass
class ProviderBundle:
    settings: Settings
    stt: STTProvider
    llm: LLMProvider
    tts: TTSProvider
    reasons: dict[str, str] = field(default_factory=dict)

    @classmethod
    def build(cls, config: Settings) -> "ProviderBundle":
        stt, stt_reason = build_stt(config)
        llm, llm_reason = build_llm(config)
        tts, tts_reason = build_tts(config)
        return cls(
            settings=config,
            stt=stt,
            llm=llm,
            tts=tts,
            reasons={"stt": stt_reason, "llm": llm_reason, "tts": tts_reason},
        )

    async def close(self) -> None:
        for provider in (self.stt, self.llm, self.tts):
            try:
                await provider.close()
            except Exception:  # pragma: no cover - best effort cleanup
                logger.debug("Provider close failed", exc_info=True)


def _bundle(websocket: WebSocket) -> ProviderBundle:
    bundle = getattr(websocket.app.state, "voice_providers", None)
    if bundle is None:
        bundle = ProviderBundle.build(settings)
        websocket.app.state.voice_providers = bundle
    return bundle


@router.get("/config")
async def voice_config(request: Request) -> dict:
    """Non-secret provider configuration for the diagnostics panel."""
    bundle: ProviderBundle = getattr(request.app.state, "voice_providers", None) or ProviderBundle.build(
        settings
    )
    return {
        "app": settings.app_name,
        "version": settings.version,
        "audio": {
            "input_sample_rate": 16_000,
            "format": "pcm16",
            "frame_ms": 20,
        },
        "stt": {"provider": bundle.stt.name, "partials": bool(getattr(bundle.stt, "supports_partials", False))},
        "llm": {"provider": bundle.llm.name},
        "tts": {"provider": bundle.tts.name, "kind": bundle.tts.kind},
        "vad": {"name": "EnergyVAD", "end_silence_ms": settings.vad_end_silence_ms},
        "targets": {
            "first_audio_p50_ms": 700,
            "first_audio_p95_ms": 1000,
            "barge_in_p95_ms": 200,
        },
    }
    return info


@router.get("/metrics")
async def voice_metrics() -> dict:
    """Aggregate latency percentiles across recent turns on this process."""
    return registry.summary()


@router.delete("/metrics")
async def reset_voice_metrics() -> dict:
    registry.reset()
    return {"status": "ok"}


def _origin_allowed(origin: str | None, allowed: tuple[str, ...]) -> bool:
    if origin is None:
        return True  # non-browser clients and the test client
    return origin in allowed or "*" in allowed


@router.websocket("/ws")
async def voice_socket(websocket: WebSocket) -> None:
    bundle = _bundle(websocket)
    origin = websocket.headers.get("origin")
    if not _origin_allowed(origin, bundle.settings.cors_origins):
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    await websocket.accept()

    transport = QueueTransport(websocket, max_queue=bundle.settings.max_output_queue)
    pipeline = VoicePipeline(
        transport=transport,
        settings=bundle.settings,
        stt=bundle.stt,
        llm=bundle.llm,
        tts=bundle.tts,
        vad=EnergyVAD(
            threshold=bundle.settings.vad_threshold,
            start_frames=bundle.settings.vad_start_frames,
            end_silence_ms=bundle.settings.vad_end_silence_ms,
            pre_roll_ms=bundle.settings.vad_pre_roll_ms,
            max_utterance_ms=bundle.settings.vad_max_utterance_ms,
        ),
    )
    logger.info(
        "voice session %s started (stt=%s llm=%s tts=%s)",
        pipeline.session.session_id[:8],
        pipeline.stt.name,
        pipeline.llm.name,
        pipeline.tts.name,
    )
    await pipeline.start()

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if (data := message.get("bytes")) is not None:
                await pipeline.feed_audio(data)
                continue
            text = message.get("text")
            if not text:
                continue
            await _handle_text(pipeline, text)
    except WebSocketDisconnect:
        pass
    except Exception:  # pragma: no cover - connection level guard
        logger.exception("Voice session failed")
    finally:
        await pipeline.close()
        await transport.close()
        runtime_ms = round((time.time() - pipeline.session.created_at) * 1000)
        logger.info(
            "voice session %s closed (turns=%s dropped_events=%s runtime_ms=%s)",
            pipeline.session.session_id[:8],
            pipeline.session.turn_count,
            transport.dropped,
            runtime_ms,
        )


async def _handle_text(pipeline: VoicePipeline, raw: str) -> None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await pipeline.transport.send(
            {"type": "error", "stage": "protocol", "message": "Invalid JSON message", "recoverable": True}
        )
        return
    if not isinstance(payload, dict):
        return

    kind = payload.get("type")
    if kind == "ping":
        await pipeline.transport.send({"type": "pong"})
    elif kind == "transcript":
        await pipeline.handle_browser_transcript(
            str(payload.get("text", "")), bool(payload.get("final", False))
        )
    elif kind == "interrupt":
        await pipeline.interrupt(str(payload.get("reason", "manual")))
    elif kind == "metrics":
        turn_id = str(payload.get("turn_id", ""))
        metrics = payload.get("metrics") or {}
        if turn_id and isinstance(metrics, dict):
            await pipeline.handle_client_metrics(turn_id, metrics)
    elif kind == "playback.done":
        return
    elif kind in {"start", "playback.start"}:
        return
    else:
        await pipeline.transport.send(
            {"type": "error", "stage": "protocol", "message": f"Unknown message type: {kind}", "recoverable": True}
        )


async def shutdown_providers(app) -> None:
    bundle = getattr(app.state, "voice_providers", None)
    if bundle is not None:
        await bundle.close()


__all__ = ["router", "ProviderBundle", "shutdown_providers"]
