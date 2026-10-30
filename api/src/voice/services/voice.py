"""Voice service orchestration for configuration and realtime sessions."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from ..audio.vad import EnergyVAD
from ..catalog.voices import build_catalog
from ..core.config import Settings, settings
from ..core.metrics import registry
from ..providers import SarvamSTT, SarvamTTS
from ..runtime.pipeline import VoicePipeline
from ..runtime.session import VoiceSession
from ..runtime.transport import QueueTransport
from ..security.rate_limit import (
    ClientSignals,
    RateLimitDecision,
    StrictRateLimiter,
    browser_client_issue,
    browser_transport_issue,
    client_ip,
)
from .provider_bundle import get_or_create_bundle

logger = logging.getLogger(__name__)


def _limiter(websocket: WebSocket) -> StrictRateLimiter:
    limiter = getattr(websocket.app.state, "rate_limiter", None)
    if limiter is None:
        limiter = StrictRateLimiter(
            get_or_create_bundle(websocket.app.state, settings).settings
        )
        websocket.app.state.rate_limiter = limiter
    return limiter


def get_config(state: Any) -> dict[str, Any]:
    """Non-secret provider configuration for the diagnostics panel."""
    bundle = get_or_create_bundle(state, settings)
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


def get_catalog() -> dict[str, Any]:
    """Return the speakers supported by the configured Sarvam TTS model."""
    return build_catalog(settings.tts_model, settings.tts_voice)


def get_metrics() -> dict[str, Any]:
    """Aggregate latency percentiles across recent turns on this process."""
    return registry.summary()


def reset_metrics() -> dict[str, str]:
    """Clear the in-memory latency registry."""
    registry.reset()
    return {"status": "ok"}


def _origin_allowed(origin: str | None, allowed: tuple[str, ...]) -> bool:
    if origin is None:
        return True  # non-browser clients and the test client
    return origin in allowed or "*" in allowed


CONFIG_WAIT_S = 2.0
MAX_EARLY_AUDIO_CHUNKS = 64


async def read_initial_config(
    websocket: WebSocket,
) -> tuple[dict[str, Any], list[bytes], bool]:
    """Read the optional ``configure`` frame before starting the pipeline.

    Audio sent immediately after the socket opens is buffered so the browser can
    start capturing while the first round trip is still in flight.
    """
    client_payload: dict[str, Any] = {}
    buffered: list[bytes] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + CONFIG_WAIT_S

    while len(buffered) < MAX_EARLY_AUDIO_CHUNKS:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            message = await asyncio.wait_for(websocket.receive(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        if message.get("type") == "websocket.disconnect":
            return client_payload, buffered, True
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
        raw_client = payload.get("client", {})
        if isinstance(raw_client, dict):
            client_payload = raw_client
        raw_credentials = payload.get("byok", payload.get("settings", {}))
        if isinstance(raw_credentials, dict) and any(
            value for value in raw_credentials.values()
        ):
            logger.warning(
                "voice configure frame included provider credentials; "
                "backend credentials are fixed by server configuration"
            )
            await websocket.send_json(
                {
                    "type": "error",
                    "stage": "config",
                    "message": (
                        "Provider credentials are not accepted by this API. "
                        "The server manages provider access."
                    ),
                    "recoverable": True,
                }
            )
        break
    return client_payload, buffered, False


async def _reject_rate_limit(
    websocket: WebSocket,
    decision: RateLimitDecision,
) -> None:
    payload = {
        "type": "error",
        "stage": "rate_limit",
        "message": decision.message,
        "retry_after_s": decision.retry_after_s,
        "code": decision.code,
        "recoverable": False,
    }
    if decision.limit > 0:
        payload["limit"] = decision.limit
    await websocket.send_json(payload)
    await websocket.close(code=1008, reason="Rate limit exceeded")


async def _reject_client(websocket: WebSocket, message: str) -> None:
    await websocket.send_json(
        {
            "type": "error",
            "stage": "client_validation",
            "message": message,
            "recoverable": False,
        }
    )
    await websocket.close(code=1008, reason="Browser client required")


async def serve_voice_socket(websocket: WebSocket) -> None:
    """Run one rate-limited realtime voice session."""
    platform_bundle = get_or_create_bundle(websocket.app.state, settings)
    limiter = _limiter(websocket)
    origin = websocket.headers.get("origin")
    client = websocket.client
    client_label = f"{client.host}:{client.port}" if client else "unknown"
    logger.info(
        "voice socket connected client=%s origin=%s", client_label, origin or "-"
    )
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

    caller_ip = client_ip(
        client.host if client else None,
        websocket.headers,
        trust_proxy_headers=platform_bundle.settings.trust_proxy_headers,
    )
    unlimited = platform_bundle.settings.ip_is_unlimited(caller_ip)
    if unlimited:
        logger.warning(
            "voice socket bypasses rate limits for allowlisted IP client=%s",
            client_label,
        )
    provisional = limiter.identity(
        ip=caller_ip,
        user_agent=websocket.headers.get("user-agent", ""),
        origin=origin or "",
        signals=ClientSignals(),
    )
    if not unlimited:
        ip_decision = await limiter.record_ip_attempt(provisional.ip_key)
        if not ip_decision.allowed:
            await _reject_rate_limit(websocket, ip_decision)
            return

    if platform_bundle.settings.require_browser_client:
        issue = browser_transport_issue(
            origin,
            websocket.headers.get("user-agent", ""),
        )
        if issue:
            await _reject_client(websocket, issue)
            return

    client_payload, early_audio, disconnected = await read_initial_config(websocket)
    if disconnected:
        logger.info(
            "voice socket disconnected client=%s before configure", client_label
        )
        return

    client_signals = ClientSignals.from_payload(client_payload)
    if platform_bundle.settings.require_browser_client:
        issue = browser_client_issue(
            origin=origin,
            user_agent=websocket.headers.get("user-agent", ""),
            signals=client_signals,
        )
        if issue:
            await _reject_client(websocket, issue)
            return

    identity = limiter.identity(
        ip=caller_ip,
        user_agent=websocket.headers.get("user-agent", ""),
        origin=origin or "",
        signals=client_signals,
    )
    identity_acquired = False
    if not unlimited:
        identity_decision = await limiter.acquire(identity)
        if not identity_decision.allowed:
            await _reject_rate_limit(websocket, identity_decision)
            return
        identity_acquired = True

        quota_decision = await limiter.check_turn(identity)
        if not quota_decision.allowed:
            await _reject_rate_limit(websocket, quota_decision)
            await limiter.release(identity)
            return

    transport: QueueTransport | None = None
    try:
        session_settings = platform_bundle.settings
        bundle = platform_bundle
        transport = QueueTransport(
            websocket, max_queue=session_settings.max_output_queue
        )
        session = VoiceSession()

        async def allow_turn() -> RateLimitDecision:
            decision = await limiter.allow_turn(identity)
            return decision

        async def guard_usage(kind: str, chars: int, tokens: int) -> str | None:
            decision = await limiter.consume_usage(
                identity,
                kind=kind,
                chars=chars,
                tokens=tokens,
            )
            if decision.allowed:
                return None
            return decision.message

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
            turn_limit=(
                None if unlimited else session_settings.platform_max_turns
            ),
            turn_guard=None if unlimited else allow_turn,
            usage_guard=None if unlimited else guard_usage,
        )
    except Exception:
        if transport is not None:
            await transport.close()
        if identity_acquired:
            await limiter.release(identity)
        raise
    logger.info(
        "voice session %s started (stt=%s llm=%s tts=%s early_audio_bytes=%d)",
        session.session_id[:8],
        pipeline.stt.name,
        pipeline.llm.name,
        pipeline.tts.name,
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
        deadline = (
            time.monotonic() + session_settings.rate_limit_max_session_seconds
            if not unlimited
            and session_settings.rate_limit_max_session_seconds > 0
            else float("inf")
        )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                await websocket.send_json(
                    {
                        "type": "error",
                        "stage": "rate_limit",
                        "message": "The maximum voice session duration was reached.",
                        "recoverable": False,
                    }
                )
                await websocket.close(
                    code=1008, reason="Session duration limit reached"
                )
                break
            try:
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "stage": "rate_limit",
                        "message": "The maximum voice session duration was reached.",
                        "recoverable": False,
                    }
                )
                await websocket.close(
                    code=1008, reason="Session duration limit reached"
                )
                break
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
            await handle_control_text(pipeline, text)
    except WebSocketDisconnect as exc:
        logger.info(
            "voice session %s websocket disconnected code=%s",
            session.session_id[:8],
            exc.code,
        )
    except Exception:  # pragma: no cover - connection level guard
        logger.exception("Voice session failed")
    finally:
        if identity_acquired:
            await limiter.release(identity)
        await pipeline.close()
        await transport.close()
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
        return (
            f"reason={str(payload.get('reason', 'manual'))[:80]!r} "
            f"turn_id={payload.get('turn_id', '')!r}"
        )
    if kind == "voice":
        return repr(str(payload.get("voice", ""))[:64])
    if kind == "metrics":
        metrics = payload.get("metrics") or {}
        keys = sorted(metrics) if isinstance(metrics, dict) else []
        return f"turn_id={payload.get('turn_id', '')!r} keys={keys}"
    if kind == "configure":
        return "(credentials omitted from logs)"
    return ""


async def handle_control_text(pipeline: VoicePipeline, raw: str) -> None:
    """Apply a validated client control frame to an active voice pipeline."""
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
        reason = payload.get("reason", "manual")
        if not isinstance(reason, str) or not reason.strip():
            reason = "manual"
        reason = reason.strip()[:64]
        turn_id = payload.get("turn_id")
        if turn_id is not None and (
            not isinstance(turn_id, str) or not 1 <= len(turn_id) <= 128
        ):
            await pipeline.transport.send(
                {
                    "type": "error",
                    "stage": "protocol",
                    "message": "Interrupt turn_id must be a non-empty string",
                    "recoverable": True,
                }
            )
            return
        await pipeline.interrupt(reason, turn_id=turn_id or None)
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
            await pipeline.prewarm_tts()
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
__all__ = [
    "get_catalog",
    "get_config",
    "get_metrics",
    "handle_control_text",
    "read_initial_config",
    "reset_metrics",
    "serve_voice_socket",
]
