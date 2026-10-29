"""Sarvam Bulbul streaming text-to-speech adapter."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncIterator
from urllib.parse import urlencode

import websockets

from ..core.config import Settings
from .base import ProviderError

logger = logging.getLogger(__name__)


class SarvamTTS:
    """Persistent Sarvam TTS WebSocket that streams raw PCM16 audio.

    The connection is created lazily and reused for every sentence in a turn.
    Sarvam has no in-band cancel, so an interrupted stream is marked dirty and
    the socket is replaced before the next synthesis request.
    """

    kind = "audio"
    name = "sarvam"

    def __init__(self, settings: Settings, session_id: str = "") -> None:
        self._settings = settings
        self._tag = f"session={session_id[:8]}" if session_id else "session=?"
        self.sample_rate = settings.tts_sample_rate
        self._ws: websockets.ClientConnection | None = None
        self._speaker: str | None = None
        self._dirty = False
        self._connect_lock = asyncio.Lock()

    def _url(self) -> str:
        query = urlencode(
            {
                "model": self._settings.tts_model,
                "send_completion_event": "true",
            }
        )
        return f"{self._settings.sarvam_ws_url}/text-to-speech/ws?{query}"

    async def _connect(self, speaker: str) -> None:
        """Open and configure the socket once, even if prewarm races synthesis."""
        async with self._connect_lock:
            await self._connect_once(speaker)

    async def _connect_once(self, speaker: str) -> None:
        if (
            self._ws is not None
            and self._ws.close_code is None
            and self._speaker == speaker
        ):
            return
        await self._close_socket()
        if not self._settings.sarvam_api_key:
            raise ProviderError("tts", "Sarvam API key is not configured.")
        logger.info(
            "%s tts connecting url=%s model=%s speaker=%s language=%s sample_rate=%d",
            self._tag,
            self._url(),
            self._settings.tts_model,
            speaker,
            self._settings.tts_language,
            self._settings.tts_sample_rate,
        )
        try:
            self._ws = await websockets.connect(
                self._url(),
                additional_headers={
                    "api-subscription-key": self._settings.sarvam_api_key
                },
                max_size=None,
                open_timeout=10,
                ping_interval=20,
                ping_timeout=20,
            )
        except Exception as exc:
            self._ws = None
            logger.error("%s tts connect failed: %s", self._tag, exc)
            raise ProviderError(
                "tts", f"Could not connect to Sarvam speech synthesis: {exc}"
            ) from exc

        config: dict[str, object] = {
            "speaker": speaker,
            # "language_code": self._settings.tts_language,
            "pace": self._settings.tts_speed,
            "speech_sample_rate": str(self._settings.tts_sample_rate),
            "output_audio_codec": "linear16",
            "min_buffer_size": 50,
            "max_chunk_length": 150,
        }
        if "v2" not in self._settings.tts_model:
            config["temperature"] = self._settings.tts_temperature
        logger.debug("%s tts -> config %s", self._tag, config)
        try:
            await self._ws.send(json.dumps({"type": "config", "data": config}))
        except Exception as exc:
            logger.error("%s tts configure failed: %s", self._tag, exc)
            await self._close_socket()
            raise ProviderError(
                "tts", f"Could not configure Sarvam speech synthesis: {exc}"
            ) from exc
        self._speaker = speaker
        logger.info("%s tts connected", self._tag)

    async def prepare(self, voice: str | None = None) -> None:
        """Open the synthesis socket before the first sentence is available."""
        speaker = (voice or self._settings.tts_voice).strip()
        async with self._connect_lock:
            if self._dirty:
                await self._close_socket()
                self._dirty = False
            await self._connect_once(speaker)

    async def _send(self, payload: dict) -> None:
        if self._ws is None or self._ws.close_code is not None:
            raise ProviderError("tts", "Sarvam speech synthesis is not connected.")
        await self._ws.send(json.dumps(payload))

    async def _stream(
        self, text: str, voice: str | None = None
    ) -> AsyncIterator[bytes]:
        speaker = (voice or self._settings.tts_voice).strip()
        async with self._connect_lock:
            if self._dirty:
                await self._close_socket()
                self._dirty = False
            await self._connect_once(speaker)

        self._dirty = True
        chunks = 0
        total_bytes = 0
        loop = asyncio.get_running_loop()
        started = loop.time()
        logger.info(
            "%s tts request voice=%s chars=%d text=%r",
            self._tag,
            speaker,
            len(text),
            text,
        )
        try:
            await self._send({"type": "text", "data": {"text": text}})
            await self._send({"type": "flush"})
            deadline = loop.time() + self._settings.tts_timeout_s
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise ProviderError("tts", "Sarvam speech synthesis timed out.")
                try:
                    raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
                except asyncio.TimeoutError as exc:
                    raise ProviderError(
                        "tts", "Sarvam speech synthesis timed out."
                    ) from exc

                try:
                    message = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    logger.debug("%s tts ignoring non-JSON frame", self._tag)
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
                            logger.debug(
                                "%s tts <- audio bytes=%d chunks=%d",
                                self._tag,
                                len(chunk),
                                chunks,
                            )
                            yield chunk
                elif kind == "event":
                    if (message.get("data") or {}).get("event_type") == "final":
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
                    detail = str(
                        (message.get("data") or {}).get("message", "unknown error")
                    )
                    logger.error("%s tts error: %s", self._tag, detail[:200])
                    raise ProviderError(
                        "tts", f"Sarvam speech synthesis failed: {detail[:200]}"
                    )
        except asyncio.CancelledError:
            self._dirty = True
            logger.info(
                "%s tts cancelled chunks=%d bytes=%d ms=%.1f",
                self._tag,
                chunks,
                total_bytes,
                (loop.time() - started) * 1000,
            )
            raise
        except websockets.ConnectionClosed as exc:
            self._dirty = True
            logger.warning("%s tts socket closed: %s", self._tag, exc)
            raise ProviderError(
                "tts", f"Sarvam speech synthesis stopped: {exc}"
            ) from exc
        finally:
            if self._dirty:
                # The next call must start from a clean socket; there is no
                # server-side cancel, so in-flight audio would otherwise leak
                # into the next reply.
                await self._close_socket()

    def synthesize(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        return self._stream(text, voice)

    async def _close_socket(self) -> None:
        ws, self._ws = self._ws, None
        if ws is None:
            return
        logger.debug("%s tts closing socket", self._tag)
        try:
            await ws.close()
        except Exception:
            pass

    async def close(self) -> None:
        await self._close_socket()
        self._speaker = None
        self._dirty = False


__all__ = ["SarvamTTS"]
