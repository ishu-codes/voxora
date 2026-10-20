"""FastAPI routes for the Voxora real-time voice service."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, replace

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect

from .config import Settings, settings
from .metrics import registry
from .pipeline import VoicePipeline
from .providers import SarvamSTT, SarvamTTS, build_llm
from .providers.base import LLMProvider
from .session import VoiceSession
from .transport import QueueTransport
from .vad import EnergyVAD
from .voices import build_catalog

logger = logging.getLogger(__name__)

router = APIRouter()


@dataclass
class ProviderBundle:
    """Provider state for one settings snapshot.

    The app-level bundle serves non-secret configuration. Every voice session
    builds a private bundle so per-user BYOK credentials never mutate shared
    state. Sarvam STT/TTS also hold one WebSocket per conversation.
    """

    settings: Settings
    llm: LLMProvider
    reasons: dict[str, str] = field(default_factory=dict)

    @classmethod
    def build(cls, config: Settings) -> ProviderBundle:
        llm, llm_reason = build_llm(config)
        return cls(settings=config, llm=llm, reasons={"llm": llm_reason})

    def new_stt(self, session_id: str = "") -> SarvamSTT:
        return SarvamSTT(self.settings, session_id)

    def new_tts(self, session_id: str = "") -> SarvamTTS:
        return SarvamTTS(self.settings, session_id)

    async def close(self) -> None:
        try:
            await self.llm.close()
        except Exception:  # pragma: no cover - best effort cleanup
            logger.debug("Provider close failed", exc_info=True)


def _clean_text(value: object, label: str, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string.")
    cleaned = value.strip()
    if len(cleaned) > limit:
        raise ValueError(f"{label} is too long.")
    if any(character in cleaned for character in "\r\n\0"):
        raise ValueError(f"{label} contains invalid characters.")
    return cleaned


@dataclass
class VoiceCredentials:
    """Optional per-session provider credentials supplied by the browser.

    Keys are held only for the lifetime of the WebSocket session. They are
    never written to disk or included in logs.
    """

    sarvam_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""

    def __post_init__(self) -> None:
        self.sarvam_api_key = self.sarvam_api_key.strip()
        self.openai_api_key = self.openai_api_key.strip()
        self.openai_base_url = self.openai_base_url.strip().rstrip("/")
        self.openai_model = self.openai_model.strip()

    @property
    def full_byok(self) -> bool:
        """True when both speech and language stages use the user's account."""
        return bool(self.sarvam_api_key) and bool(
            self.openai_api_key or self.openai_base_url
        )

    @classmethod
    def from_payload(cls, payload: object) -> VoiceCredentials:
        if not isinstance(payload, dict):
            raise ValueError("Provider settings must be an object.")
        base_url = _clean_text(payload.get("openai_base_url"), "OpenAI base URL", 2_048)
        if base_url and not base_url.startswith(("http://", "https://")):
            raise ValueError("OpenAI base URL must start with http:// or https://.")
        return cls(
            sarvam_api_key=_clean_text(
                payload.get("sarvam_api_key"), "Sarvam API key", 512
            ),
            openai_api_key=_clean_text(
                payload.get("openai_api_key"), "OpenAI API key", 512
            ),
            openai_base_url=base_url.rstrip("/"),
            openai_model=_clean_text(
                payload.get("openai_model"), "OpenAI model", 160
            ),
        )

    def apply(self, base: Settings) -> Settings:
        updates: dict[str, object] = {}
        if self.sarvam_api_key:
            updates["sarvam_api_key"] = self.sarvam_api_key
        if self.openai_api_key:
            updates["llm_api_key"] = self.openai_api_key
        if self.openai_base_url:
            updates["llm_base_url"] = self.openai_base_url
        if self.openai_model:
            updates["llm_model"] = self.openai_model
        if self.openai_api_key or self.openai_base_url:
            updates["llm_provider"] = "openai"
        return replace(base, **updates)


def _bundle(websocket: WebSocket) -> ProviderBundle:
    bundle = getattr(websocket.app.state, "voice_providers", None)
    if bundle is None:
        bundle = ProviderBundle.build(settings)
        websocket.app.state.voice_providers = bundle
    return bundle


@router.get("/config")
async def voice_config(request: Request) -> dict:
    """Non-secret provider configuration for the diagnostics panel."""
    bundle: ProviderBundle = getattr(
        request.app.state, "voice_providers", None
    ) or ProviderBundle.build(settings)
    return {
        "app": settings.app_name,
        "version": settings.version,
        "audio": {
            "input_sample_rate": 16_000,
            "format": "pcm16",
            "frame_ms": 20,
        },
        "stt": {
            "provider": SarvamSTT.name,
            "model": settings.stt_model,
            "language": settings.stt_language,
            "partials": SarvamSTT.supports_partials,
        },
        "llm": {"provider": bundle.llm.name},
        "tts": {
            "provider": SarvamTTS.name,
            "kind": SarvamTTS.kind,
            "model": settings.tts_model,
            "voice": settings.tts_voice,
            "language": settings.tts_language,
            "sample_rate": settings.tts_sample_rate,
        },
        "vad": {"name": "EnergyVAD", "end_silence_ms": settings.vad_end_silence_ms},
        "targets": {
            "first_audio_p50_ms": 700,
            "first_audio_p95_ms": 1000,
            "barge_in_p95_ms": 200,
        },
    }


@router.get("/voices")
async def voice_catalog(response: Response) -> dict:
    """Return the speakers supported by the configured Sarvam TTS model.

    The browser caches this catalog locally; the HTTP headers let proxies and
    the browser HTTP cache reuse it for a day as well.
    """
    response.headers["Cache-Control"] = (
        "public, max-age=86400, stale-while-revalidate=604800"
    )
    return build_catalog(settings.tts_model, settings.tts_voice)


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


CONFIG_WAIT_S = 2.0
MAX_EARLY_AUDIO_CHUNKS = 64


async def _read_initial_config(
    websocket: WebSocket,
) -> tuple[VoiceCredentials, list[bytes], bool]:
    """Read the optional ``configure`` frame before starting the pipeline.

    Audio sent immediately after the socket opens is buffered so the browser can
    start capturing while the first round trip is still in flight.
    """
    credentials = VoiceCredentials()
    buffered: list[bytes] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + CONFIG_WAIT_S

    while len(buffered) < MAX_EARLY_AUDIO_CHUNKS:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            message = await asyncio.wait_for(
                websocket.receive(), timeout=remaining
            )
        except asyncio.TimeoutError:
            break
        if message.get("type") == "websocket.disconnect":
            return credentials, buffered, True
        if (data := message.get("bytes")) is not None:
            buffered.append(data)
            continue
        text = message.get("text")
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            break
        if not isinstance(payload, dict) or payload.get("type") != "configure":
            break
        raw = payload.get("byok", payload.get("settings", {}))
        try:
            credentials = VoiceCredentials.from_payload(raw)
        except ValueError as exc:
            logger.warning("voice configure frame rejected: %s", exc)
            await websocket.send_json(
                {
                    "type": "error",
                    "stage": "config",
                    "message": str(exc),
                    "recoverable": True,
                }
            )
        else:
            logger.info(
                "voice configure frame received (sarvam_key=%s llm_key=%s llm_base_url=%s llm_model=%s)",
                bool(credentials.sarvam_api_key),
                bool(credentials.openai_api_key),
                credentials.openai_base_url or "-",
                credentials.openai_model or "-",
            )
        break
    return credentials, buffered, False


@router.websocket("/ws")
async def voice_socket(websocket: WebSocket) -> None:
    platform_bundle = _bundle(websocket)
    origin = websocket.headers.get("origin")
    client = websocket.client
    client_label = f"{client.host}:{client.port}" if client else "unknown"
    logger.info("voice socket connected client=%s origin=%s", client_label, origin or "-")
    if not _origin_allowed(origin, platform_bundle.settings.cors_origins):
        logger.warning(
            "voice socket rejected client=%s origin=%s (not allowed)",
            client_label,
            origin or "-",
        )
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    await websocket.accept()
    logger.info("voice socket accepted client=%s", client_label)

    credentials, early_audio, disconnected = await _read_initial_config(websocket)
    if disconnected:
        logger.info("voice socket disconnected client=%s before configure", client_label)
        return

    session_settings = credentials.apply(platform_bundle.settings)
    bundle = ProviderBundle.build(session_settings)
    transport = QueueTransport(
        websocket, max_queue=session_settings.max_output_queue
    )
    session = VoiceSession()
    pipeline = VoicePipeline(
        transport=transport,
        settings=session_settings,
        stt=bundle.new_stt(session.session_id),
        llm=bundle.llm,
        tts=bundle.new_tts(session.session_id),
        vad=EnergyVAD(
            threshold=session_settings.vad_threshold,
            start_frames=session_settings.vad_start_frames,
            end_silence_ms=session_settings.vad_end_silence_ms,
            pre_roll_ms=session_settings.vad_pre_roll_ms,
            max_utterance_ms=session_settings.vad_max_utterance_ms,
        ),
        session=session,
        turn_limit=None
        if credentials.full_byok
        else session_settings.platform_max_turns,
    )
    logger.info(
        "voice session %s started (stt=%s llm=%s tts=%s byok=%s early_audio_bytes=%d)",
        session.session_id[:8],
        pipeline.stt.name,
        pipeline.llm.name,
        pipeline.tts.name,
        credentials.full_byok,
        sum(len(chunk) for chunk in early_audio),
    )

    try:
        await pipeline.start(bundle.reasons)
        for chunk in early_audio:
            logger.debug(
                "voice session %s feeding early audio bytes=%d",
                session.session_id[:8],
                len(chunk),
            )
            await pipeline.feed_audio(chunk)
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                logger.info(
                    "voice session %s received disconnect code=%s",
                    session.session_id[:8],
                    message.get("code"),
                )
                break
            if (data := message.get("bytes")) is not None:
                logger.debug(
                    "voice session %s <- audio bytes=%d",
                    session.session_id[:8],
                    len(data),
                )
                await pipeline.feed_audio(data)
                continue
            text = message.get("text")
            if not text:
                continue
            await _handle_text(pipeline, text)
    except WebSocketDisconnect as exc:
        logger.info(
            "voice session %s websocket disconnected code=%s",
            session.session_id[:8],
            exc.code,
        )
    except Exception:  # pragma: no cover - connection level guard
        logger.exception("Voice session failed")
    finally:
        await pipeline.close()
        await transport.close()
        await bundle.close()
        runtime_ms = round((time.time() - pipeline.session.created_at) * 1000)
        logger.info(
            "voice session %s closed (turns=%s dropped_events=%s runtime_ms=%s client=%s)",
            pipeline.session.session_id[:8],
            pipeline.session.turn_count,
            transport.dropped,
            runtime_ms,
            client_label,
        )


def _describe_control(kind: object, payload: dict) -> str:
    """Summarise a client control frame without leaking credentials."""
    if kind == "interrupt":
        return repr(str(payload.get("reason", "manual"))[:80])
    if kind == "voice":
        return repr(str(payload.get("voice", ""))[:64])
    if kind == "metrics":
        metrics = payload.get("metrics") or {}
        keys = sorted(metrics) if isinstance(metrics, dict) else []
        return f"turn_id={payload.get('turn_id', '')!r} keys={keys}"
    if kind == "configure":
        return "(credentials omitted from logs)"
    return ""


async def _handle_text(pipeline: VoicePipeline, raw: str) -> None:
    tag = f"session={pipeline.session.session_id[:8]}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("%s <- invalid JSON control message", tag)
        await pipeline.transport.send(
            {
                "type": "error",
                "stage": "protocol",
                "message": "Invalid JSON message",
                "recoverable": True,
            }
        )
        return
    if not isinstance(payload, dict):
        logger.warning("%s <- non-object control message", tag)
        return

    kind = payload.get("type")
    if kind == "ping":
        logger.debug("%s <- ping", tag)
    else:
        detail = _describe_control(kind, payload)
        logger.info("%s <- %s%s", tag, kind, f" {detail}" if detail else "")

    if kind == "ping":
        await pipeline.transport.send({"type": "pong"})
    elif kind == "configure":
        await pipeline.transport.send(
            {
                "type": "error",
                "stage": "config",
                "message": "Provider settings must be sent before the session starts.",
                "recoverable": True,
            }
        )
    elif kind == "interrupt":
        await pipeline.interrupt(str(payload.get("reason", "manual")))
    elif kind == "voice":
        voice = payload.get("voice")
        if (
            not isinstance(voice, str)
            or not 1 <= len(voice) <= 64
            or not all(char.isalnum() or char in "-_" for char in voice)
        ):
            await pipeline.transport.send(
                {
                    "type": "error",
                    "stage": "protocol",
                    "message": "Voice must be 1-64 letters, digits, dashes or underscores",
                    "recoverable": True,
                }
            )
        else:
            pipeline.set_voice(voice)
    elif kind == "metrics":
        turn_id = str(payload.get("turn_id", ""))
        metrics = payload.get("metrics") or {}
        if turn_id and isinstance(metrics, dict):
            await pipeline.handle_client_metrics(turn_id, metrics)
    elif kind == "playback.done" or kind in {"start", "playback.start"}:
        return
    else:
        await pipeline.transport.send(
            {
                "type": "error",
                "stage": "protocol",
                "message": f"Unknown message type: {kind}",
                "recoverable": True,
            }
        )


async def shutdown_providers(app) -> None:
    bundle = getattr(app.state, "voice_providers", None)
    if bundle is not None:
        await bundle.close()


__all__ = [
    "ProviderBundle",
    "VoiceCredentials",
    "router",
    "shutdown_providers",
]
