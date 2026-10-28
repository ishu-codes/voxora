"""Sarvam Bulbul WebSocket text-to-speech adapter."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from urllib.parse import urlencode

import websockets

from bench.core.config import BenchmarkConfig
from bench.providers.base import BenchmarkProviderError, TTSResult


class SarvamTTS:
    name = "sarvam"

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self.model = str(config.tts["model"])
        self._socket: websockets.ClientConnection | None = None
        self._configured_language: str | None = None
        self._lock = asyncio.Lock()
        self._timeout = float(config.tts["timeout_s"])

    def _url(self) -> str:
        query = urlencode(
            {"model": self.model, "send_completion_event": "true"}
        )
        return f"{self.config.sarvam_ws_url}/text-to-speech/ws?{query}"

    async def _connect(self, language: str) -> None:
        if not self.config.sarvam_api_key:
            raise BenchmarkProviderError(
                "Sarvam API key is not configured. Set SARVAM_API_KEY."
            )
        if (
            self._socket is not None
            and self._socket.close_code is None
            and self._configured_language == language
        ):
            return
        await self.close()
        try:
            self._socket = await websockets.connect(
                self._url(),
                additional_headers={
                    "api-subscription-key": self.config.sarvam_api_key
                },
                max_size=None,
                open_timeout=10,
                ping_interval=20,
                ping_timeout=20,
            )
        except Exception as exc:
            if "403" in str(exc):
                raise BenchmarkProviderError(
                    "Sarvam authentication failed (HTTP 403). "
                    "Set a valid SARVAM_API_KEY in api/.env."
                ) from exc
            raise BenchmarkProviderError(
                f"Could not connect to Sarvam TTS: {exc}"
            ) from exc
        config: dict[str, object] = {
            "speaker": str(self.config.tts["speaker"]),
            "language_code": language,
            "pace": float(self.config.tts["pace"]),
            "speech_sample_rate": str(self.config.tts["sample_rate_hz"]),
            "output_audio_codec": "linear16",
            "min_buffer_size": 50,
            "max_chunk_length": 150,
        }
        if "v2" not in self.model:
            config["temperature"] = float(self.config.tts["temperature"])
        await self._socket.send(json.dumps({"type": "config", "data": config}))
        self._configured_language = language

    async def _synthesize_once(
        self,
        text: str,
        language: str,
        request_sent: float,
    ) -> TTSResult:
        loop = asyncio.get_running_loop()
        await self._connect(language)
        assert self._socket is not None
        try:
            await self._socket.send(
                json.dumps({"type": "text", "data": {"text": text}})
            )
            await self._socket.send(json.dumps({"type": "flush"}))
            audio = bytearray()
            first_audio: float | None = None
            deadline = loop.time() + self._timeout
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise BenchmarkProviderError("Sarvam TTS timed out.")
                raw = await asyncio.wait_for(
                    self._socket.recv(),
                    timeout=remaining,
                )
                message = json.loads(raw)
                kind = message.get("type")
                if kind == "audio":
                    encoded = (message.get("data") or {}).get("audio")
                    if encoded:
                        chunk = base64.b64decode(encoded)
                        if chunk:
                            if first_audio is None:
                                first_audio = time.perf_counter()
                            audio.extend(chunk)
                elif kind == "event":
                    event_type = (message.get("data") or {}).get("event_type")
                    if event_type == "final":
                        finished = time.perf_counter()
                        if first_audio is None:
                            raise BenchmarkProviderError(
                                "Sarvam TTS returned no audio."
                            )
                        return TTSResult(
                            audio_bytes=bytes(audio),
                            t_request_sent=request_sent,
                            t_first_audio_byte=first_audio,
                            t_done=finished,
                        )
                elif kind == "error":
                    detail = (message.get("data") or {}).get(
                        "message",
                        "unknown error",
                    )
                    raise BenchmarkProviderError(
                        f"Sarvam TTS failed: {detail}"
                    )
        except websockets.ConnectionClosed as exc:
            await self.close()
            raise BenchmarkProviderError(
                f"Sarvam TTS connection closed: {exc}"
            ) from exc
        except asyncio.TimeoutError as exc:
            await self.close()
            raise BenchmarkProviderError("Sarvam TTS timed out.") from exc

    async def synthesize(self, text: str, language: str) -> TTSResult:
        if not text.strip():
            raise BenchmarkProviderError("Cannot synthesize empty text.")
        request_sent = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(self.config.retry_attempts):
            try:
                async with self._lock:
                    return await self._synthesize_once(
                        text,
                        language,
                        request_sent,
                    )
            except BenchmarkProviderError as exc:
                last_error = exc
                message = str(exc).lower()
                if "authentication" in message or "credits exhausted" in message:
                    raise
                await self.close()
                if attempt + 1 >= self.config.retry_attempts:
                    break
                delay = min(
                    self.config.retry_base_delay * (2**attempt),
                    self.config.retry_max_delay,
                )
                await asyncio.sleep(delay)
        raise BenchmarkProviderError(
            f"Sarvam TTS failed after retries: {last_error}"
        ) from last_error

    async def close(self) -> None:
        socket, self._socket = self._socket, None
        self._configured_language = None
        if socket is not None:
            try:
                await socket.close()
            except Exception:
                pass


__all__ = ["SarvamTTS"]
