"""Sarvam Saaras realtime WebSocket speech-to-text adapter."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import websockets

from bench.core.config import BenchmarkConfig
from bench.providers.base import BenchmarkProviderError, STTResult
from bench.utils.audio import convert_to_pcm16_mono, wav_properties

_MODE_LANGUAGE = {
    "en": "en-IN",
    "hi": "hi-IN",
    "hinglish": "hi-IN",
}


def _auth_message(detail: str) -> BenchmarkProviderError:
    return BenchmarkProviderError(
        "Sarvam authentication failed (HTTP 403). "
        "Set a valid SARVAM_API_KEY in api/.env."
    )


@dataclass
class _SocketState:
    socket: websockets.ClientConnection
    reader: asyncio.Task[None]
    events: asyncio.Queue[dict]


class SarvamSTT:
    name = "sarvam"

    def __init__(self, config: BenchmarkConfig, mode: str) -> None:
        self.config = config
        self.mode = mode
        self.model = str(config.stt["model"])
        self._sample_rate = int(config.raw["benchmark"]["sample_rate_hz"])
        self._timeout = float(config.stt["timeout_s"])
        self._last_connection = 0.0
        self._connections: dict[str, _SocketState] = {}

    def metadata(self, language_hint: str | None) -> dict[str, object]:
        return {
            "device": "cloud",
            "compute_type": None,
            "model_size": self.model,
            "beam_size": None,
            "language_hint": {"en": "en", "hi": "hi", "hinglish": "hi"}.get(
                language_hint or ""
            ),
            "declared_sample_rate_hz": self._sample_rate,
        }

    def _url(self, language_code: str, sample_rate: int) -> str:
        query = urlencode(
            {
                "language_code": language_code,
                "model": self.model,
                "stream_type": str(self.config.stt["stream_type"]),
                "mode": self.mode,
                "endpointing": "manual",
                "encoding": "linear16",
                "sample_rate": sample_rate,
            }
        )
        return f"{self.config.sarvam_ws_url}/speech-to-text-realtime/ws?{query}"

    async def _read_socket(
        self,
        socket: websockets.ClientConnection,
        events: asyncio.Queue[dict],
    ) -> None:
        try:
            async for raw in socket:
                try:
                    message = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                await events.put(message)
        except asyncio.CancelledError:
            raise
        except websockets.ConnectionClosed as exc:
            await events.put(
                {
                    "event": "__closed__",
                    "code": exc.code,
                    "message": exc.reason or str(exc),
                }
            )

    async def _ensure_connection(
        self,
        connection_key: str,
        language_code: str,
        sample_rate: int,
    ) -> _SocketState:
        existing = self._connections.get(connection_key)
        if existing is not None and existing.socket.close_code is None:
            return existing
        if existing is not None:
            await self._drop_connection(connection_key)
        if not self.config.sarvam_api_key:
            raise BenchmarkProviderError(
                "Sarvam API key is not configured. Set SARVAM_API_KEY."
            )
        loop = asyncio.get_running_loop()
        remaining_spacing = (
            self._last_connection
            + self.config.websocket_connection_spacing
            - loop.time()
        )
        if remaining_spacing > 0:
            await asyncio.sleep(remaining_spacing)
        self._last_connection = loop.time()
        try:
            socket = await websockets.connect(
                self._url(language_code, sample_rate),
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
                raise _auth_message(str(exc)) from exc
            raise BenchmarkProviderError(
                f"Could not connect to Sarvam STT: {exc}"
            ) from exc
        events: asyncio.Queue[dict] = asyncio.Queue()
        reader = asyncio.create_task(self._read_socket(socket, events))
        state = _SocketState(socket=socket, reader=reader, events=events)
        self._connections[connection_key] = state
        return state

    async def _drop_connection(self, language_code: str) -> None:
        state = self._connections.pop(language_code, None)
        if state is None:
            return
        state.reader.cancel()
        await asyncio.gather(state.reader, return_exceptions=True)
        try:
            await state.socket.close()
        except Exception:
            pass

    async def _one_attempt(
        self,
        wav_path: str,
        language_code: str,
        request_sent: float,
        realtime: bool,
    ) -> STTResult:
        source_rate = wav_properties(wav_path)[0]
        sample_rate = 8000 if source_rate == 8000 else 16000
        connection_key = f"{language_code}:{sample_rate}"
        audio = convert_to_pcm16_mono(wav_path, sample_rate)
        state = await self._ensure_connection(
            connection_key,
            language_code,
            sample_rate,
        )
        socket = state.socket
        events = state.events
        loop = asyncio.get_running_loop()
        first_partial: float | None = None
        audio_end: float | None = None
        try:
            await socket.send(json.dumps({"event": "speech_start"}))
            # 100 ms chunks keep the upload paced while completing each short
            # utterance quickly enough for a practical benchmark.
            chunk_size = sample_rate // 10 * 2
            for offset in range(0, len(audio.pcm), chunk_size):
                chunk_started = loop.time()
                chunk = audio.pcm[offset : offset + chunk_size]
                await socket.send(
                    json.dumps(
                        {
                            "event": "audio_input",
                            "audio": base64.b64encode(chunk).decode("ascii"),
                        }
                    )
                )
                if realtime:
                    await asyncio.sleep(
                        max(0.0, 0.1 - (loop.time() - chunk_started))
                    )
                else:
                    await asyncio.sleep(0.01)
            audio_end = loop.time()
            await socket.send(json.dumps({"event": "speech_end"}))

            deadline = loop.time() + self._timeout
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise BenchmarkProviderError("Sarvam STT timed out.")
                try:
                    event = await asyncio.wait_for(events.get(), timeout=remaining)
                except asyncio.TimeoutError as exc:
                    raise BenchmarkProviderError("Sarvam STT timed out.") from exc
                kind = event.get("event")
                if kind == "transcript.partial" and first_partial is None:
                    if str(event.get("text", "")).strip():
                        first_partial = time.perf_counter()
                elif kind == "transcript.final":
                    finished = time.perf_counter()
                    return STTResult(
                        text=str(event.get("text", "")).strip(),
                        t_request_sent=request_sent,
                        t_first_partial=first_partial,
                        t_final=finished,
                        provider=self.name,
                        model=self.model,
                        mode=self.mode,
                        t_audio_end=audio_end,
                    )
                elif kind == "error":
                    if event.get("is_fatal"):
                        raise BenchmarkProviderError(
                            f"Sarvam STT error: {event.get('message', 'unknown')}"
                        )
                elif kind == "__closed__":
                    raise BenchmarkProviderError(
                        "Sarvam STT connection closed "
                        f"({event.get('code')}): {event.get('message')}"
                    )
        except Exception:
            await self._drop_connection(connection_key)
            raise

    async def transcribe_file(
        self,
        wav_path: str,
        language_hint: str | None,
        *,
        realtime: bool = False,
    ) -> STTResult:
        language_code = _MODE_LANGUAGE.get(
            language_hint or "",
            str(self.config.stt.get("language") or "auto"),
        )
        request_sent = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(self.config.retry_attempts):
            try:
                return await self._one_attempt(
                    wav_path,
                    language_code,
                    request_sent,
                    realtime,
                )
            except BenchmarkProviderError as exc:
                if "authentication" in str(exc).lower():
                    raise
                last_error = exc
                if attempt + 1 >= self.config.retry_attempts:
                    break
                rate_limited = any(
                    marker in str(exc).lower()
                    for marker in ("rate limit", " 1003", "(1003)")
                )
                delay = min(
                    self.config.retry_base_delay
                    * (2 ** (attempt + (1 if rate_limited else 0))),
                    self.config.retry_max_delay,
                )
                await asyncio.sleep(delay)
        raise BenchmarkProviderError(
            f"Sarvam STT failed after retries: {last_error}"
        ) from last_error

    async def close(self) -> None:
        for language_code in list(self._connections):
            await self._drop_connection(language_code)


__all__ = ["SarvamSTT"]
