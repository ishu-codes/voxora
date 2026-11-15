"""Gnani Prisma v2.5 realtime speech-to-text adapter."""

from __future__ import annotations

import asyncio
import json
import logging
import re

import websockets

from ..core.config import SAMPLE_RATE, Settings
from .base import PartialCallback, ProviderError

logger = logging.getLogger(__name__)

_GNANI_FRAME_BYTES = 1_024


def gnani_http_error(stage: str, status: int, body: str = "") -> ProviderError:
    """Convert documented Gnani status codes into a safe user-facing error."""
    if status in {401, 403}:
        return ProviderError(
            stage,
            "Gnani authentication failed. Check GNANI_API_KEY and its API scopes.",
        )
    if status == 402:
        return ProviderError(stage, "Gnani credits are exhausted.")
    if status == 429:
        return ProviderError(stage, "Gnani rate limit reached. Retrying shortly.")
    detail = _error_detail(body)
    suffix = f": {detail}" if detail else ""
    return ProviderError(stage, f"Gnani {stage.upper()} failed ({status}){suffix}")


def _error_detail(body: str) -> str:
    """Extract a short message from Gnani's two documented error envelopes."""
    try:
        payload = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        return " ".join((body or "").split())[:200]
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("type") or "")[:200]
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("error_code") or "")[:200]
    return str(payload.get("message") or "")[:200]


def _status_from_exception(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status
    match = re.search(r"\b(401|402|403|429|500|502|503|504)\b", str(exc))
    return int(match.group(1)) if match else None


class GnaniSTT:
    """Persistent Prisma v2.5 stream with a commit per Voxora utterance.

    Voxora's energy VAD owns turn boundaries. Prisma requires 1,024-byte PCM
    frames, so incoming 640-byte frames are rebuffered and the final partial
    frame is zero-padded before ``commit``.
    """

    name = "gnani"
    supports_partials = False

    def __init__(self, settings: Settings, session_id: str = "") -> None:
        self._settings = settings
        self._tag = f"session={session_id[:8]}" if session_id else "session=?"
        self._ws: websockets.ClientConnection | None = None
        self._reader: asyncio.Task[None] | None = None
        self._events: asyncio.Queue[dict] = asyncio.Queue()
        self._pcm = bytearray()
        self._active = False
        self._closing = False
        self._last_segment = 0
        self._audio_bytes = 0
        self._started_at = 0.0
        self.detected_language: str | None = None

    @property
    def language(self) -> str:
        return self._settings.gnani_stt_language

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key-id": self._settings.gnani_api_key,
            "model": self._settings.gnani_stt_model,
            "language_code": self.language,
            "format": self._settings.gnani_stt_format,
            "x-sample-rate": str(SAMPLE_RATE),
            "x-idle-timeout-sec": "900",
            "x-min-silence-ms": "500",
            "x-max-speech-s": "30",
        }

    async def _connect(self) -> None:
        if self._ws is not None and self._ws.close_code is None:
            return
        if not self._settings.gnani_api_key:
            raise ProviderError("stt", "Gnani API key is not configured.")
        await self._reset()
        last_error: Exception | None = None
        attempts = max(1, self._settings.provider_retry_attempts)
        for attempt in range(attempts):
            try:
                self._ws = await websockets.connect(
                    self._settings.gnani_stt_url,
                    additional_headers=self._headers(),
                    max_size=None,
                    open_timeout=10,
                    ping_interval=20,
                    ping_timeout=20,
                )
                break
            except Exception as exc:
                last_error = exc
                status = _status_from_exception(exc)
                if status in {401, 402, 403}:
                    raise gnani_http_error("stt", status) from exc
                if attempt + 1 >= attempts:
                    if status is not None:
                        raise gnani_http_error("stt", status, str(exc)) from exc
                    raise ProviderError(
                        "stt",
                        f"Could not connect to Gnani speech recognition: {exc}",
                    ) from exc
                delay = (
                    self._settings.provider_retry_base_ms
                    * (2**attempt)
                    / 1000
                )
                logger.warning(
                    "%s stt connect attempt=%d failed: %s; retrying in %.2fs",
                    self._tag,
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
        if self._ws is None:
            raise ProviderError(
                "stt",
                f"Could not connect to Gnani speech recognition: {last_error}",
            )
        self._events = asyncio.Queue()
        self._reader = asyncio.create_task(self._read_loop(self._ws))
        logger.info(
            "%s stt connected endpoint=%s model=%s language=%s",
            self._tag,
            self._settings.gnani_stt_url,
            self._settings.gnani_stt_model,
            self.language,
        )

    async def _read_loop(self, ws: websockets.ClientConnection) -> None:
        try:
            async for raw in ws:
                try:
                    message = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(message, dict):
                    continue
                kind = message.get("type")
                logger.debug("%s stt <- %s", self._tag, kind)
                if kind == "connected":
                    logger.info(
                        "%s stt ready sample_rate=%s chunk_size=%s",
                        self._tag,
                        (message.get("config") or {}).get("sample_rate"),
                        (message.get("config") or {}).get("chunk_size"),
                    )
                    continue
                if kind in {"processing", "speech_start", "settings_updated"}:
                    continue
                await self._events.put(message)
        except asyncio.CancelledError:
            raise
        except websockets.ConnectionClosed as exc:
            if not self._closing:
                await self._events.put(
                    {
                        "type": "__closed__",
                        "message": f"connection closed ({exc.code})",
                    }
                )
        except Exception as exc:
            if not self._closing:
                await self._events.put(
                    {
                        "type": "__closed__",
                        "message": f"connection failed: {exc}",
                    }
                )
        finally:
            self._reader = None

    async def begin_utterance(self, on_partial: PartialCallback | None = None) -> None:
        del on_partial  # Prisma v2.5 streaming emits final segments only.
        if self._active:
            await self.cancel_utterance()
        await self._connect()
        self._pcm.clear()
        self._audio_bytes = 0
        self._active = True
        self._started_at = asyncio.get_running_loop().time()
        logger.info(
            "%s stt begin utterance after_segment=%d",
            self._tag,
            self._last_segment,
        )

    async def push_audio(self, pcm: bytes) -> None:
        if not pcm or not self._active:
            return
        self._pcm.extend(pcm)
        self._audio_bytes += len(pcm)
        while len(self._pcm) >= _GNANI_FRAME_BYTES:
            frame = bytes(self._pcm[:_GNANI_FRAME_BYTES])
            del self._pcm[:_GNANI_FRAME_BYTES]
            await self._send_audio(frame)

    async def _send_audio(self, frame: bytes) -> None:
        if self._ws is None or self._ws.close_code is not None:
            raise ProviderError("stt", "Gnani speech recognition is not connected.")
        await self._ws.send(frame)

    async def end_utterance(self) -> str:
        if not self._active:
            return ""
        self._active = False
        frame = bytes(self._pcm)
        self._pcm.clear()
        if frame:
            await self._send_audio(
                frame + b"\x00" * (_GNANI_FRAME_BYTES - len(frame))
            )
        if self._ws is None or self._ws.close_code is not None:
            await self._reset()
            raise ProviderError("stt", "Gnani speech recognition is not connected.")
        await self._ws.send(json.dumps({"type": "commit"}))

        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._settings.stt_timeout_s
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                await self._reset()
                raise ProviderError("stt", "Gnani transcription timed out.")
            try:
                message = await asyncio.wait_for(
                    self._events.get(),
                    timeout=remaining,
                )
            except asyncio.TimeoutError as exc:
                await self._reset()
                raise ProviderError("stt", "Gnani transcription timed out.") from exc
            kind = message.get("type")
            if kind == "__closed__":
                await self._reset()
                raise ProviderError(
                    "stt",
                    f"Gnani speech recognition stopped: {message.get('message', '')}",
                )
            if kind == "error":
                detail = str(message.get("message") or "unknown error")[:200]
                await self._reset()
                raise ProviderError("stt", f"Gnani transcription failed: {detail}")
            if kind != "transcript":
                continue
            try:
                segment = int(message.get("segment_index", 0))
            except (TypeError, ValueError):
                segment = 0
            if segment <= self._last_segment:
                continue
            self._last_segment = segment
            detected = message.get("detected_language_code")
            if isinstance(detected, str) and detected.strip():
                self.detected_language = detected.strip()
            text = str(message.get("text") or "").strip()
            elapsed_ms = round((loop.time() - self._started_at) * 1000, 1)
            logger.info(
                "%s stt final segment=%d ms=%.1f chars=%d audio_bytes=%d",
                self._tag,
                segment,
                elapsed_ms,
                len(text),
                self._audio_bytes,
            )
            return text

    async def cancel_utterance(self) -> None:
        if not self._active and self._ws is None:
            return
        logger.info(
            "%s stt cancel utterance audio_bytes=%d",
            self._tag,
            self._audio_bytes,
        )
        self._active = False
        self._pcm.clear()
        # A fresh stream is the only reliable way to discard a segment already
        # committed by the server.
        await self._reset()

    async def _reset(self) -> None:
        self._closing = True
        if self._reader is not None:
            self._reader.cancel()
            await asyncio.gather(self._reader, return_exceptions=True)
            self._reader = None
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        self._events = asyncio.Queue()
        self._pcm.clear()
        self._active = False
        self._closing = False

    async def close(self) -> None:
        await self._reset()


__all__ = ["GnaniSTT", "gnani_http_error"]
