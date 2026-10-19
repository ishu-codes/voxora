"""The cancellable streaming pipeline: VAD -> STT -> LLM -> TTS -> browser.

A single :class:`VoicePipeline` instance owns one conversation.  It keeps the
stages decoupled: it never imports a model SDK, it only calls the provider
interfaces.  Turn generation is referenced by an integer so that audio produced
by a cancelled turn can be dropped by both sides.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any, Callable

from .audio import pcm16_rms
from .config import FRAME_BYTES, SAMPLE_RATE, Settings
from .metrics import MetricsRegistry, registry as default_registry
from .providers.base import LLMProvider, ProviderError, STTProvider, TTSProvider
from .sentence import SentenceChunker
from .session import VoiceSession
from .transport import Transport
from .vad import EnergyVAD, VAD

logger = logging.getLogger(__name__)

BROWSER_STT_NAMES = {"browser"}


def _ms(start: float, end: float) -> float:
    return round((end - start) * 1000.0, 1)


class VoicePipeline:
    def __init__(
        self,
        transport: Transport,
        settings: Settings,
        stt: STTProvider,
        llm: LLMProvider,
        tts: TTSProvider,
        *,
        vad: VAD | None = None,
        metrics: MetricsRegistry | None = None,
        session: VoiceSession | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport
        self.settings = settings
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.session = session or VoiceSession()
        self.metrics = metrics or default_registry
        self.clock = clock
        self.vad: VAD = vad or EnergyVAD(
            threshold=settings.vad_threshold,
            start_frames=settings.vad_start_frames,
            end_silence_ms=settings.vad_end_silence_ms,
            pre_roll_ms=settings.vad_pre_roll_ms,
            max_utterance_ms=settings.vad_max_utterance_ms,
        )

        self._frame_buffer = bytearray()
        self._generation = 0
        self._turn_task: asyncio.Task[None] | None = None
        self._task_turn_id: int | None = None
        self._turns: dict[int, dict[str, Any]] = {}
        self._awaiting_transcript: asyncio.Future[str] | None = None
        self._pending_transcript: str | None = None
        self._state = "idle"
        self._last_level_at = 0.0
        self._closed = False

    # ------------------------------------------------------------------ setup

    @property
    def mode(self) -> str:
        return "browser-stt" if self.stt.name in BROWSER_STT_NAMES else "server-stt"

    def ready_event(self, reasons: dict[str, str] | None = None) -> dict[str, Any]:
        reasons = reasons or {}
        return {
            "type": "ready",
            "session_id": self.session.session_id,
            "audio": {
                "format": "pcm16",
                "input_sample_rate": SAMPLE_RATE,
                "frame_ms": 20,
            },
            "stt": {
                "name": self.stt.name,
                "partials": bool(getattr(self.stt, "supports_partials", False)),
                "mode": self.mode,
                "reason": reasons.get("stt", ""),
            },
            "llm": {"name": self.llm.name, "reason": reasons.get("llm", "")},
            "tts": {
                "name": self.tts.name,
                "kind": self.tts.kind,
                "sample_rate": self.tts.sample_rate,
                "reason": reasons.get("tts", ""),
            },
            "vad": {
                "name": type(self.vad).__name__,
                "threshold": self.settings.vad_threshold,
                "end_silence_ms": self.settings.vad_end_silence_ms,
            },
            "targets": {
                "first_audio_p50_ms": 700,
                "first_audio_p95_ms": 1000,
                "barge_in_p95_ms": 200,
            },
        }

    async def start(self) -> None:
        await self.transport.send(self.ready_event())
        await self._set_state("listening")

    # ------------------------------------------------------------ audio input

    async def feed_audio(self, data: bytes) -> None:
        if not data or self._closed:
            return
        self._frame_buffer.extend(data)
        while len(self._frame_buffer) >= FRAME_BYTES:
            frame = bytes(self._frame_buffer[:FRAME_BYTES])
            del self._frame_buffer[:FRAME_BYTES]
            await self._process_frame(frame)

    async def _process_frame(self, frame: bytes) -> None:
        events = self.vad.process(frame)
        for event in events:
            if event.kind == "speech_start":
                await self._on_speech_start()
            elif event.kind == "speech_end":
                await self._on_speech_end(event.audio, event.duration_ms)
        await self._maybe_send_level(frame)

    async def _maybe_send_level(self, frame: bytes) -> None:
        now = self.clock()
        if now - self._last_level_at < 0.1:
            return
        self._last_level_at = now
        await self.transport.send(
            {
                "type": "audio.level",
                "rms": round(pcm16_rms(frame), 4),
                "speech": self.vad.is_speech,
            }
        )

    async def _on_speech_start(self) -> None:
        self._generation += 1
        self._pending_transcript = None

        if self._turn_task is not None and not self._turn_task.done():
            self._turn_task.cancel()
            await self.transport.send(
                {
                    "type": "turn.cancelled",
                    "turn_id": self._label(self._task_turn_id or 0),
                    "reason": "barge_in",
                }
            )

        await self.transport.send({"type": "speech.start", "turn_id": self._label(self._generation)})
        await self._set_state("listening")

    async def _on_speech_end(self, audio: bytes, duration_ms: float) -> None:
        generation = self._generation
        turn_id = self._label(generation)
        ts_end = self.clock()
        self._turns[generation] = {
            "turn_id": turn_id,
            "speech_duration_ms": round(duration_ms, 1),
            "requested_at": ts_end,
            "stt": self.stt.name,
            "llm": self.llm.name,
            "tts": self.tts.name,
        }
        await self._set_state("thinking", generation)

        self._turn_task = asyncio.create_task(self._handle_turn(generation, audio, ts_end))
        self._task_turn_id = generation

    # --------------------------------------------------------------- turn run

    async def _handle_turn(self, generation: int, audio: bytes, ts_end: float) -> None:
        try:
            text = await self._transcribe(generation, audio, ts_end)
            if generation != self._generation:
                return
            if not text:
                await self.transport.send({"type": "turn.empty", "turn_id": self._label(generation)})
                await self._set_state("listening", generation)
                return

            await self.transport.send(
                {"type": "transcript.final", "turn_id": self._label(generation), "text": text}
            )
            self.session.add("user", text)
            self.session.turn_count += 1
            await self._run_assistant(generation, text, ts_end)
        except asyncio.CancelledError:
            raise
        except ProviderError as exc:
            await self._fail(generation, exc.stage, exc.message)
        except asyncio.TimeoutError:
            await self._fail(generation, "pipeline", "The pipeline stage timed out.")
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unhandled pipeline error")
            await self._fail(generation, "internal", str(exc) or "Internal error")
        finally:
            if self._task_turn_id == generation:
                self._turn_task = None
                self._task_turn_id = None

    async def _transcribe(self, generation: int, audio: bytes, ts_end: float) -> str:
        if self.mode == "browser-stt":
            text = await self._await_browser_transcript()
        else:
            started = self.clock()
            try:
                text = await asyncio.wait_for(
                    self.stt.transcribe(audio, SAMPLE_RATE),
                    timeout=30.0,
                )
            finally:
                self._turns[generation]["stt_ms"] = _ms(started, self.clock())
            await self.transport.send(
                {"type": "transcript.partial", "text": text, "final": True}
            )
        return (text or "").strip()

    async def _await_browser_transcript(self) -> str:
        if self._pending_transcript:
            text, self._pending_transcript = self._pending_transcript, None
            return text
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._awaiting_transcript = future
        try:
            return await asyncio.wait_for(
                future, timeout=self.settings.browser_transcript_timeout_s
            )
        except asyncio.TimeoutError:
            return ""
        finally:
            self._awaiting_transcript = None

    async def _run_assistant(self, generation: int, user_text: str, ts_end: float) -> None:
        turn = self._turns[generation]
        messages = self.session.messages_for_llm(self.settings.system_prompt)
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=16)
        tokens: list[str] = []
        llm_started = self.clock()
        first_token_at: float | None = None
        first_audio_at: float | None = None
        sentence_index = 0

        async def produce() -> None:
            nonlocal first_token_at
            chunker = SentenceChunker()
            try:
                async for token in self.llm.stream(messages):
                    if generation != self._generation:
                        break
                    if first_token_at is None:
                        first_token_at = self.clock()
                        turn["llm_first_token_ms"] = _ms(llm_started, first_token_at)
                    tokens.append(token)
                    await self.transport.send(
                        {"type": "assistant.delta", "turn_id": self._label(generation), "text": token}
                    )
                    for sentence in chunker.feed(token):
                        await queue.put(sentence)
                tail = chunker.flush()
                if tail and generation == self._generation:
                    await queue.put(tail)
            finally:
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

        async def consume() -> None:
            nonlocal first_audio_at, sentence_index
            while True:
                sentence = await queue.get()
                if sentence is None:
                    break
                if generation != self._generation:
                    break
                if self.tts.kind == "browser":
                    if first_audio_at is None:
                        first_audio_at = self.clock()
                        turn["tts_first_audio_ms"] = 0.0
                        turn["e2e_first_audio_ms"] = _ms(ts_end, first_audio_at)
                        await self._set_state("speaking", generation)
                    await self.transport.send(
                        {
                            "type": "speak.chunk",
                            "turn_id": self._label(generation),
                            "text": sentence,
                            "index": sentence_index,
                        }
                    )
                    sentence_index += 1
                else:
                    tts_started = self.clock()
                    async for chunk in self.tts.synthesize(sentence):
                        if generation != self._generation:
                            return
                        if first_audio_at is None:
                            first_audio_at = self.clock()
                            turn["tts_first_audio_ms"] = _ms(tts_started, first_audio_at)
                            turn["e2e_first_audio_ms"] = _ms(ts_end, first_audio_at)
                            await self._set_state("speaking", generation)
                        await self.transport.send(
                            {
                                "type": "audio.chunk",
                                "turn_id": self._label(generation),
                                "data": base64.b64encode(chunk).decode("ascii"),
                                "sample_rate": self.tts.sample_rate,
                                "format": "pcm16",
                            }
                        )

        await self._gather(produce(), consume())

        if generation != self._generation:
            return

        if self.tts.kind == "browser":
            await self.transport.send({"type": "speak.end", "turn_id": self._label(generation)})

        full_text = "".join(tokens).strip()
        if full_text:
            self.session.add("assistant", full_text)

        turn["total_ms"] = _ms(ts_end, self.clock())
        self.metrics.record(turn)

        await self.transport.send(
            {"type": "assistant.done", "turn_id": self._label(generation), "text": full_text}
        )
        await self.transport.send(
            {
                "type": "turn.metrics",
                "turn_id": self._label(generation),
                "metrics": {
                    key: turn.get(key)
                    for key in (
                        "speech_duration_ms",
                        "stt_ms",
                        "llm_first_token_ms",
                        "tts_first_audio_ms",
                        "e2e_first_audio_ms",
                        "total_ms",
                    )
                },
            }
        )
        await self._set_state("listening", generation)

    async def _gather(self, *coroutines) -> None:
        tasks = [asyncio.create_task(coroutine) for coroutine in coroutines]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def _fail(self, generation: int, stage: str, message: str) -> None:
        turn = self._turns.get(generation)
        if turn is not None:
            turn["error"] = f"{stage}: {message}"[:300]
            self.metrics.record(turn)
        await self.transport.send(
            {
                "type": "error",
                "turn_id": self._label(generation),
                "stage": stage,
                "message": message,
                "recoverable": True,
            }
        )
        await self.transport.send({"type": "assistant.failed", "turn_id": self._label(generation)})
        await self._set_state("listening", generation)

    # ------------------------------------------------------------ client input

    async def handle_browser_transcript(self, text: str, final: bool) -> None:
        text = (text or "").strip()
        if not text:
            return
        if not final:
            await self.transport.send({"type": "transcript.partial", "text": text})
            return
        future = self._awaiting_transcript
        if future is not None and not future.done():
            future.set_result(text)
        else:
            self._pending_transcript = text

    async def handle_client_metrics(self, turn_id: str, payload: dict[str, Any]) -> None:
        allowed = {
            key: value
            for key, value in payload.items()
            if key in {"first_playback_ms", "barge_in_ms", "playback_ms"} and isinstance(value, (int, float))
        }
        if allowed:
            self.metrics.merge(turn_id, allowed)

    async def interrupt(self, reason: str = "manual") -> None:
        task = self._turn_task
        if task is not None and not task.done():
            self._generation += 1
            task.cancel()
            await self.transport.send(
                {
                    "type": "turn.cancelled",
                    "turn_id": self._label(self._task_turn_id or 0),
                    "reason": reason,
                }
            )
        self.vad.reset()
        self._pending_transcript = None
        await self._set_state("listening")

    # ------------------------------------------------------------------ utils

    async def _set_state(self, state: str, generation: int | None = None) -> None:
        if state == self._state:
            return
        self._state = state
        await self.transport.send(
            {
                "type": "state",
                "state": state,
                "turn_id": self._label(generation if generation is not None else self._generation),
            }
        )

    def _label(self, generation: int) -> str:
        return f"{self.session.session_id[:8]}-{generation}"

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._turn_task is not None and not self._turn_task.done():
            self._turn_task.cancel()
            try:
                await self._turn_task
            except (asyncio.CancelledError, Exception):
                pass

    async def close_providers(self) -> None:
        for provider in (self.stt, self.llm, self.tts):
            try:
                await provider.close()
            except Exception:  # pragma: no cover - best effort cleanup
                logger.debug("Provider close failed", exc_info=True)


__all__ = ["VoicePipeline"]
