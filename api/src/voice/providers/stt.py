"""Sarvam Saaras streaming speech-to-text adapter."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from urllib.parse import urlencode

import websockets

from ..config import SAMPLE_RATE, Settings
from .base import PartialCallback, ProviderError

logger = logging.getLogger(__name__)

_AUDIO_INPUT = "audio_input"


class SarvamSTT:
    """Persistent WebSocket connection to Sarvam's realtime transcription API.

    Endpointing is ``manual``: the pipeline's energy VAD decides when speech
    starts and ends, and this adapter forwards that decision to Sarvam. One
    instance belongs to one voice session.
    """

    name = "sarvam"
    supports_partials = True

    def __init__(self, settings: Settings, session_id: str = "") -> None:
        self._settings = settings
        self._tag = f"session={session_id[:8]}" if session_id else "session=?"
        self._ws: websockets.ClientConnection | None = None
        self._reader: asyncio.Task[None] | None = None
        self._events: asyncio.Queue[dict] = asyncio.Queue()
        self._on_partial: PartialCallback | None = None
        self._pending_idx: int | None = None
        self._next_idx = 0
        self._active = False
        self._closing = False
        self._error: ProviderError | None = None
        self._audio_bytes = 0
        self._utterance_started = 0.0

    def _url(self) -> str:
        query = urlencode(
            {
                "language_code": self._settings.stt_language,
                "model": self._settings.stt_model,
                "stream_type": self._settings.stt_stream_type,
                "mode": self._settings.stt_mode,
                "endpointing": "manual",
                "encoding": "linear16",
                "sample_rate": SAMPLE_RATE,
            }
        )
        return f"{self._settings.sarvam_ws_url}/speech-to-text-realtime/ws?{query}"

    async def _connect(self) -> None:
        if self._ws is not None and self._ws.close_code is None:
            return
        if not self._settings.sarvam_api_key:
            raise ProviderError("stt", "Sarvam API key is not configured.")
        await self._reset()
        logger.info(
            "%s stt connecting url=%s model=%s language=%s stream_type=%s mode=%s",
            self._tag,
            self._url(),
            self._settings.stt_model,
            self._settings.stt_language,
            self._settings.stt_stream_type,
            self._settings.stt_mode,
        )
        try:
            self._ws = await websockets.connect(
                self._url(),
                additional_headers={"api-subscription-key": self._settings.sarvam_api_key},
                max_size=None,
                open_timeout=10,
                ping_interval=20,
                ping_timeout=20,
            )
        except Exception as exc:
            self._ws = None
            logger.error("%s stt connect failed: %s", self._tag, exc)
            raise ProviderError(
                "stt", f"Could not connect to Sarvam speech recognition: {exc}"
            ) from exc
        self._events = asyncio.Queue()
        self._reader = asyncio.create_task(self._read_loop(self._ws))
        logger.info("%s stt connected", self._tag)

    async def _read_loop(self, ws: websockets.ClientConnection) -> None:
        try:
            async for raw in ws:
                try:
                    message = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    logger.debug("%s stt ignoring non-JSON frame", self._tag)
                    continue
                logger.debug("%s stt <- %s", self._tag, message)
                await self._handle_message(message)
        except asyncio.CancelledError:
            raise
        except websockets.ConnectionClosed as exc:
            if not self._closing:
                logger.warning(
                    "%s stt socket closed code=%s reason=%s",
                    self._tag,
                    exc.code,
                    exc.reason or "-",
                )
                await self._events.put(
                    {"event": "__closed__", "message": f"connection closed ({exc.code})"}
                )
        except Exception as exc:  # pragma: no cover - defensive
            if not self._closing:
                logger.error("%s stt reader failed: %s", self._tag, exc)
                await self._events.put(
                    {"event": "__closed__", "message": f"connection failed: {exc}"}
                )
        finally:
            self._reader = None

    async def _handle_message(self, message: dict) -> None:
        event = message.get("event")
        if event == "transcript.partial":
            text = str(message.get("text", "")).strip()
            idx = message.get("utterance_idx")
            logger.debug(
                "%s stt partial idx=%s accepted=%s text=%r",
                self._tag,
                idx,
                bool(text)
                and self._on_partial is not None
                and self._pending_idx is not None
                and idx == self._pending_idx,
                text,
            )
            if (
                text
                and self._on_partial is not None
                and self._pending_idx is not None
                and idx == self._pending_idx
            ):
                await self._on_partial(text)
            return
        if event == "session.begin":
            logger.info("%s stt session begin config=%s", self._tag, message.get("config"))
            return
        if event == "session.end":
            logger.info(
                "%s stt session end utterances=%s audio_duration_s=%s",
                self._tag,
                message.get("total_utterances"),
                message.get("audio_duration_s"),
            )
            return
        if event in {"vad.speech_start", "vad.speech_end", "pong"}:
            return
        self._events.put_nowait(message)

    async def _send(self, payload: dict) -> None:
        if self._ws is None or self._ws.close_code is not None:
            raise ProviderError("stt", "Sarvam speech recognition is not connected.")
        await self._ws.send(json.dumps(payload))

    async def begin_utterance(self, on_partial: PartialCallback | None = None) -> None:
        self._error = None
        if self._active:
            await self._reset()
        await self._connect()
        self._on_partial = on_partial
        self._pending_idx = self._next_idx
        self._next_idx += 1
        self._active = True
        self._audio_bytes = 0
        self._utterance_started = asyncio.get_running_loop().time()
        logger.info(
            "%s stt begin utterance idx=%d partials=%s",
            self._tag,
            self._pending_idx,
            on_partial is not None,
        )
        try:
            await self._send({"event": "speech_start"})
        except Exception as exc:
            logger.error("%s stt speech_start failed: %s", self._tag, exc)
            await self._reset()
            raise ProviderError("stt", f"Could not start Sarvam transcription: {exc}") from exc

    async def push_audio(self, pcm: bytes) -> None:
        if not pcm or not self._active or self._error is not None:
            return
        self._audio_bytes += len(pcm)
        logger.debug(
            "%s stt -> audio bytes=%d utterance_bytes=%d",
            self._tag,
            len(pcm),
            self._audio_bytes,
        )
        try:
            await self._send(
                {
                    "event": _AUDIO_INPUT,
                    "audio": base64.b64encode(pcm).decode("ascii"),
                }
            )
        except Exception as exc:
            logger.error("%s stt audio upload failed: %s", self._tag, exc)
            self._error = ProviderError("stt", f"Sarvam audio upload failed: {exc}")
            await self._reset()

    async def end_utterance(self) -> str:
        if self._error is not None:
            error, self._error = self._error, None
            logger.error("%s stt utterance failed: %s", self._tag, error.message)
            raise error
        if not self._active or self._ws is None:
            logger.warning("%s stt end called without an active utterance", self._tag)
            return ""

        idx = self._pending_idx
        self._active = False
        loop = asyncio.get_running_loop()
        logger.info(
            "%s stt end utterance idx=%s audio_bytes=%d",
            self._tag,
            idx,
            self._audio_bytes,
        )
        try:
            await self._send({"event": "speech_end"})
        except Exception as exc:
            logger.error("%s stt speech_end failed: %s", self._tag, exc)
            await self._reset()
            raise ProviderError("stt", f"Sarvam transcription failed: {exc}") from exc

        deadline = loop.time() + self._settings.stt_timeout_s
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                logger.error("%s stt final timed out after %.1fs", self._tag, self._settings.stt_timeout_s)
                await self._reset()
                raise ProviderError("stt", "Sarvam transcription timed out.")
            try:
                message = await asyncio.wait_for(self._events.get(), timeout=remaining)
            except asyncio.TimeoutError:
                logger.error("%s stt final timed out after %.1fs", self._tag, self._settings.stt_timeout_s)
                await self._reset()
                raise ProviderError("stt", "Sarvam transcription timed out.")

            event = message.get("event")
            if event == "__closed__":
                logger.error("%s stt socket stopped while awaiting final", self._tag)
                await self._reset()
                raise ProviderError(
                    "stt", f"Sarvam speech recognition stopped: {message.get('message', '')}"
                )
            if event == "error":
                if message.get("is_fatal"):
                    detail = str(message.get("message", "unknown error"))
                    logger.error("%s stt fatal error: %s", self._tag, detail)
                    await self._reset()
                    raise ProviderError("stt", f"Sarvam transcription failed: {detail}")
                logger.warning("%s stt non-fatal error: %s", self._tag, message.get("message"))
                continue
            if event != "transcript.final":
                logger.debug("%s stt ignoring event while awaiting final: %s", self._tag, event)
                continue
            try:
                final_idx = int(message.get("utterance_idx", -1))
            except (TypeError, ValueError):
                final_idx = -1
            if idx is not None and final_idx != idx:
                logger.debug(
                    "%s stt dropping stale final idx=%s expected=%s",
                    self._tag,
                    final_idx,
                    idx,
                )
                continue  # stale final from an interrupted utterance
            text = str(message.get("text", "")).strip()
            elapsed_ms = round((loop.time() - self._utterance_started) * 1000, 1)
            self._on_partial = None
            self._pending_idx = None
            logger.info(
                "%s stt final idx=%s ms=%s chars=%d text=%r",
                self._tag,
                final_idx,
                elapsed_ms,
                len(text),
                text,
            )
            return text

    async def cancel_utterance(self) -> None:
        if not self._active:
            return
        logger.info(
            "%s stt cancel utterance idx=%s audio_bytes=%d",
            self._tag,
            self._pending_idx,
            self._audio_bytes,
        )
        self._active = False
        self._on_partial = None
        self._pending_idx = None
        try:
            await self._send({"event": "speech_end"})
        except Exception as exc:
            logger.warning("%s stt cancel failed: %s", self._tag, exc)
            await self._reset()

    async def _reset(self) -> None:
        self._closing = True
        if self._reader is not None:
            self._reader.cancel()
            try:
                await self._reader
            except (asyncio.CancelledError, Exception):
                pass
            self._reader = None
        ws, self._ws = self._ws, None
        if ws is not None:
            logger.debug("%s stt closing socket", self._tag)
            try:
                await ws.close()
            except Exception:
                pass
        self._events = asyncio.Queue()
        self._on_partial = None
        self._pending_idx = None
        self._next_idx = 0
        self._active = False
        self._audio_bytes = 0
        self._closing = False

    async def close(self) -> None:
        await self._reset()


__all__ = ["SarvamSTT"]
