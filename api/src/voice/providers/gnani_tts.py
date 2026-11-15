"""Gnani Timbre v2.5 realtime text-to-speech adapter."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncIterator

import websockets

from ..core.config import Settings
from .base import ProviderError
from .gnani_stt import _status_from_exception, gnani_http_error

logger = logging.getLogger(__name__)


class GnaniTTS:
    """Persistent Timbre v2.5 socket that streams raw PCM16 chunks."""

    kind = "audio"
    name = "gnani"

    def __init__(self, settings: Settings, session_id: str = "") -> None:
        self._settings = settings
        self._tag = f"session={session_id[:8]}" if session_id else "session=?"
        self.sample_rate = settings.tts_sample_rate
        self._ws: websockets.ClientConnection | None = None
        self._voice: str | None = None
        self._dirty = False
        self._connect_lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()

    async def _connect_once(self, voice: str) -> None:
        if (
            self._ws is not None
            and self._ws.close_code is None
            and self._voice == voice
        ):
            return
        await self._close_socket()
        if not self._settings.gnani_api_key:
            raise ProviderError("tts", "Gnani API key is not configured.")
        last_error: Exception | None = None
        attempts = max(1, self._settings.provider_retry_attempts)
        for attempt in range(attempts):
            try:
                self._ws = await websockets.connect(
                    self._settings.gnani_tts_url,
                    additional_headers={
                        "X-API-Key-ID": self._settings.gnani_api_key,
                    },
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
                    raise gnani_http_error("tts", status) from exc
                if attempt + 1 >= attempts:
                    if status is not None:
                        raise gnani_http_error("tts", status, str(exc)) from exc
                    raise ProviderError(
                        "tts",
                        f"Could not connect to Gnani speech synthesis: {exc}",
                    ) from exc
                delay = (
                    self._settings.provider_retry_base_ms
                    * (2**attempt)
                    / 1000
                )
                logger.warning(
                    "%s tts connect attempt=%d failed: %s; retrying in %.2fs",
                    self._tag,
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
        if self._ws is None:
            raise ProviderError(
                "tts",
                f"Could not connect to Gnani speech synthesis: {last_error}",
            )
        self._voice = voice
        logger.info(
            "%s tts connected endpoint=%s model=%s voice=%s language=%s",
            self._tag,
            self._settings.gnani_tts_url,
            self._settings.gnani_tts_model,
            voice,
            self._settings.gnani_tts_language,
        )

    async def prepare(self, voice: str | None = None) -> None:
        selected = (voice or self._settings.gnani_tts_voice).strip()
        async with self._request_lock:
            async with self._connect_lock:
                if self._dirty:
                    await self._close_socket()
                    self._dirty = False
                await self._connect_once(selected)

    def _request(self, text: str, voice: str) -> dict[str, object]:
        return {
            "text": text,
            "voice": voice,
            "model": self._settings.gnani_tts_model,
            "language": self._settings.gnani_tts_language,
            "speed": max(0.85, min(1.15, self._settings.tts_speed)),
            "audio_config": {
                "sample_rate": self.sample_rate,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "pcm_s16le",
                "container": "raw",
            },
        }

    async def _stream_once(
        self,
        text: str,
        voice: str,
    ) -> AsyncIterator[bytes]:
        async with self._request_lock:
            async for chunk in self._stream_locked(text, voice):
                yield chunk

    async def _stream_locked(
        self,
        text: str,
        voice: str,
    ) -> AsyncIterator[bytes]:
        async with self._connect_lock:
            if self._dirty:
                await self._close_socket()
                self._dirty = False
            await self._connect_once(voice)
        ws = self._ws
        if ws is None or ws.close_code is not None:
            raise ProviderError("tts", "Gnani speech synthesis is not connected.")

        self._dirty = True
        loop = asyncio.get_running_loop()
        started = loop.time()
        await ws.send(json.dumps(self._request(text, voice)))
        deadline = started + self._settings.tts_timeout_s
        chunks = 0
        total_bytes = 0
        logger.info(
            "%s tts request voice=%s chars=%d text=%r",
            self._tag,
            voice,
            len(text),
            text,
        )
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise ProviderError("tts", "Gnani speech synthesis timed out.")
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                try:
                    message = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(message, dict):
                    continue
                kind = message.get("type")
                if kind == "audio":
                    data = message.get("data") or {}
                    encoded = data.get("audio")
                    if encoded:
                        chunk = base64.b64decode(encoded)
                        if chunk:
                            chunks += 1
                            total_bytes += len(chunk)
                            yield chunk
                elif kind == "complete":
                    self._dirty = False
                    logger.info(
                        "%s tts done chunks=%d bytes=%d ms=%.1f",
                        self._tag,
                        chunks,
                        total_bytes,
                        (loop.time() - started) * 1000,
                    )
                    return
                elif kind == "error":
                    detail = str(message.get("message") or "unknown error")[:200]
                    raise ProviderError(
                        "tts",
                        f"Gnani speech synthesis failed: {detail}",
                    )
        except asyncio.TimeoutError as exc:
            raise ProviderError("tts", "Gnani speech synthesis timed out.") from exc
        except websockets.ConnectionClosed as exc:
            raise ProviderError(
                "tts",
                f"Gnani speech synthesis stopped: {exc}",
            ) from exc
        finally:
            if self._dirty:
                await self._close_socket()

    async def _stream(
        self,
        text: str,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        selected = (voice or self._settings.gnani_tts_voice).strip()
        attempts = max(1, self._settings.provider_retry_attempts)
        for attempt in range(attempts):
            yielded = False
            try:
                async for chunk in self._stream_once(text, selected):
                    yielded = True
                    yield chunk
                return
            except ProviderError as exc:
                message = exc.message.lower()
                if (
                    yielded
                    or "authentication" in message
                    or "credits" in message
                    or attempt + 1 >= attempts
                ):
                    raise
                delay = (
                    self._settings.provider_retry_base_ms
                    * (2**attempt)
                    / 1000
                )
                logger.warning(
                    "%s tts attempt=%d failed: %s; retrying in %.2fs",
                    self._tag,
                    attempt + 1,
                    exc.message,
                    delay,
                )
                await asyncio.sleep(delay)

    def synthesize(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        return self._stream(text, voice)

    async def _close_socket(self) -> None:
        ws, self._ws = self._ws, None
        self._voice = None
        if ws is None:
            return
        try:
            await ws.close()
        except Exception:
            pass

    async def close(self) -> None:
        await self._close_socket()
        self._dirty = False


__all__ = ["GnaniTTS"]
