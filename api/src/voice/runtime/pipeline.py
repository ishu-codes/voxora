"""The cancellable streaming pipeline: VAD -> STT -> LLM -> TTS -> browser.

A single :class:`VoicePipeline` instance owns one conversation. It keeps the
stages decoupled: it never imports a model SDK, it only calls the provider
interfaces. Turn generation is referenced by an integer so that audio produced
by a cancelled turn can be dropped by both sides.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from ..audio.processing import pcm16_rms
from ..audio.sentence import SentenceChunker
from ..audio.vad import VAD, EnergyVAD
from ..core.config import FRAME_BYTES, SAMPLE_RATE, Settings
from ..core.metrics import MetricsRegistry
from ..core.metrics import registry as default_registry
from ..providers.base import LLMProvider, ProviderError, STTProvider, TTSProvider
from ..security.rate_limit import RateLimitDecision
from .session import VoiceSession
from .transport import Transport

logger = logging.getLogger(__name__)

# How long an interrupted turn gets to unwind before the receive loop moves on.
# Provider sockets may not cancel instantly, so stale output is still gated by
# the generation counter rather than by this timeout.
_CANCEL_GRACE_S = 0.5


class UsageLimitExceeded(RuntimeError):
    pass


def _ms(start: float, end: float) -> float:
    return round((end - start) * 1000.0, 1)


def _clip(text: str, limit: int = 500) -> str:
    """Keep logs readable without hiding which text was processed."""
    return text if len(text) <= limit else f"{text[:limit]}... ({len(text)} chars)"


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
        turn_limit: int | None = None,
        turn_guard: Callable[
            [], Awaitable[RateLimitDecision | str | None]
        ] | None = None,
        usage_guard: Callable[[str, int, int], Awaitable[str | None]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport
        self.settings = settings
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self._voice: str | None = None
        self.turn_limit = turn_limit
        self.turn_guard = turn_guard
        self.usage_guard = usage_guard
        self.session = session or VoiceSession()
        self._tag = f"session={self.session.session_id[:8]}"
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
        # Tasks that outlived _CANCEL_GRACE_S. They are still reaped on close so
        # a provider that ignores cancellation cannot run past the session.
        self._orphan_tasks: set[asyncio.Task[None]] = set()
        self._turns: dict[int, dict[str, Any]] = {}
        self._stt_error: ProviderError | None = None
        self._state = "idle"
        self._last_level_at = 0.0
        self._closed = False
        self._accepting_audio = True
        self._tts_prewarm_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------ setup

    @property
    def mode(self) -> str:
        return "server-stt"

    def set_voice(self, voice: str | None) -> None:
        """Select a Sarvam speaker for subsequent sentences."""
        cleaned = (voice or "").strip()
        self._voice = cleaned or None

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
                "language": getattr(self.stt, "language", self.settings.stt_language),
                "reason": reasons.get("stt", ""),
            },
            "llm": {"name": self.llm.name, "reason": reasons.get("llm", "")},
            "tts": {
                "name": self.tts.name,
                "kind": self.tts.kind,
                "sample_rate": self.tts.sample_rate,
                "voice": self._voice or self.settings.tts_voice,
                "reason": reasons.get("tts", ""),
            },
            "vad": {
                "name": type(self.vad).__name__,
                "threshold": self.settings.vad_threshold,
                "end_silence_ms": self.settings.vad_end_silence_ms,
            },
            "platform": {
                "limited": self.turn_limit is not None,
                "turn_limit": self.turn_limit,
                "window_seconds": 60 * 60 if self.turn_limit is not None else None,
            },
            "targets": {
                "first_audio_p50_ms": 700,
                "first_audio_p95_ms": 1000,
                "barge_in_p95_ms": 200,
            },
        }

    async def start(self, reasons: dict[str, str] | None = None) -> None:
        await self.transport.send(self.ready_event(reasons))
        await self._set_state("listening")

    def _schedule_tts_prewarm(self) -> None:
        if self._tts_prewarm_task is not None and not self._tts_prewarm_task.done():
            return
        self._tts_prewarm_task = asyncio.create_task(self.prewarm_tts())

    async def prewarm_tts(self) -> None:
        """Warm TTS without making ready delivery wait on the provider."""
        try:
            await self.tts.prepare(self._voice)
        except ProviderError as exc:
            # The first synthesis retries lazily and can surface the real error
            # in the turn that needs it. A warmup failure must not end the call.
            logger.info("%s tts prewarm skipped: %s", self._tag, exc.message)
        except Exception:
            logger.warning("%s tts prewarm failed", self._tag, exc_info=True)

    # ------------------------------------------------------------ audio input

    async def feed_audio(self, data: bytes) -> None:
        if not data or self._closed or not self._accepting_audio:
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
                await self._on_speech_start(event.audio)
            elif event.kind == "speech_end":
                await self.stt.push_audio(frame)
                await self._on_speech_end(event.duration_ms)
        if not events and self.vad.is_speech:
            await self.stt.push_audio(frame)
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

    async def _on_speech_start(self, pre_roll: bytes) -> None:
        cancelled_turn = await self._cancel_turn("barge_in")
        self._generation += 1
        generation = self._generation
        self._stt_error = None
        logger.info(
            "%s speech start turn=%s pre_roll_bytes=%d cancelled=%s",
            self._tag,
            self._label(generation),
            len(pre_roll),
            cancelled_turn or "-",
        )

        await self.transport.send(
            {"type": "speech.start", "turn_id": self._label(generation)}
        )
        await self._set_state("listening")
        self._schedule_tts_prewarm()

        async def on_partial(text: str) -> None:
            if generation == self._generation:
                await self.transport.send(
                    {"type": "transcript.partial", "text": text, "final": False}
                )

        try:
            await self.stt.begin_utterance(on_partial)
            if pre_roll:
                await self.stt.push_audio(pre_roll)
        except ProviderError as exc:
            logger.error("%s stt begin failed: %s", self._tag, exc.message)
            self._stt_error = exc
            await self.transport.send(
                {
                    "type": "error",
                    "turn_id": self._label(generation),
                    "stage": exc.stage,
                    "message": exc.message,
                    "recoverable": True,
                }
            )

    async def _on_speech_end(self, duration_ms: float) -> None:
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
        await self.transport.send(
            {
                "type": "turn.timing",
                "turn_id": turn_id,
                "stage": "speech_end",
            }
        )
        await self._set_state("thinking", generation)
        logger.info(
            "%s speech end turn=%s duration_ms=%.1f",
            self._tag,
            turn_id,
            duration_ms,
        )

        self._turn_task = asyncio.create_task(self._handle_turn(generation, ts_end))
        self._task_turn_id = generation

    # --------------------------------------------------------------- turn run

    async def _handle_turn(self, generation: int, ts_end: float) -> None:
        try:
            text = await self._transcribe(generation, ts_end)
            if generation != self._generation:
                logger.debug(
                    "%s dropping stale turn=%s", self._tag, self._label(generation)
                )
                return
            if not text:
                logger.info(
                    "%s turn=%s empty transcript", self._tag, self._label(generation)
                )
                await self.transport.send(
                    {"type": "turn.empty", "turn_id": self._label(generation)}
                )
                await self._set_state("listening", generation)
                return

            logger.info(
                "%s turn=%s user_text=%r",
                self._tag,
                self._label(generation),
                _clip(text),
            )
            await self.transport.send(
                {
                    "type": "transcript.final",
                    "turn_id": self._label(generation),
                    "text": text,
                }
            )
            self._schedule_tts_prewarm()
            if self.turn_guard is not None:
                guard_result = await self.turn_guard()
                if isinstance(guard_result, str):
                    decision = RateLimitDecision.deny(
                        guard_result,
                        60 * 60,
                        code="trial_exhausted",
                    )
                elif guard_result is not None and not guard_result.allowed:
                    decision = guard_result
                else:
                    decision = None
                if decision is not None:
                    await self.transport.send(
                        {
                            "type": "error",
                            "turn_id": self._label(generation),
                            "stage": "quota",
                            "code": decision.code or "trial_exhausted",
                            "message": decision.message,
                            "retry_after_s": decision.retry_after_s,
                            "limit": self.settings.rate_limit_platform_turns_hour,
                            "recoverable": False,
                        }
                    )
                    await self._set_state("listening", generation)
                    # Stop accepting audio immediately even if a malicious
                    # client ignores the quota event. This prevents repeat STT
                    # calls until the browser closes or reconnects.
                    self._accepting_audio = False
                    return
            if (
                self.turn_limit is not None
                and self.session.turn_count >= self.turn_limit
            ):
                await self.transport.send(
                    {
                        "type": "error",
                        "turn_id": self._label(generation),
                        "stage": "quota",
                        "code": "trial_exhausted",
                        "message": (
                            "The shared platform trial has reached its turn limit. "
                            "Add your Sarvam key and an OpenAI-compatible endpoint "
                            "in Settings to keep talking without platform limits."
                        ),
                        "retry_after_s": 60 * 60,
                        "limit": self.turn_limit,
                        "recoverable": False,
                    }
                )
                await self._set_state("listening", generation)
                self._accepting_audio = False
                return
            await self._consume_usage("stt", chars=len(text))
            self.session.add("user", text)
            self.session.turn_count += 1
            await self._run_assistant(generation, text, ts_end)
        except asyncio.CancelledError:
            raise
        except ProviderError as exc:
            await self._fail(generation, exc.stage, exc.message)
        except UsageLimitExceeded as exc:
            await self._fail(generation, "rate_limit", str(exc))
        except asyncio.TimeoutError:
            await self._fail(generation, "pipeline", "The pipeline stage timed out.")
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unhandled pipeline error")
            await self._fail(generation, "internal", str(exc) or "Internal error")
        finally:
            if self._task_turn_id == generation:
                self._turn_task = None
                self._task_turn_id = None

    async def _transcribe(self, generation: int, ts_end: float) -> str:
        error, self._stt_error = self._stt_error, None
        if error is not None:
            raise error
        started = self.clock()
        try:
            text = await self.stt.end_utterance()
        finally:
            self._turns[generation]["stt_ms"] = _ms(started, self.clock())
        logger.info(
            "%s stt result turn=%s text=%r",
            self._tag,
            self._label(generation),
            _clip((text or "").strip()),
        )
        return (text or "").strip()

    async def _run_assistant(
        self, generation: int, user_text: str, ts_end: float
    ) -> None:
        turn = self._turns[generation]
        messages = self.session.messages_for_llm(self.settings.system_prompt)
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=16)
        tokens: list[str] = []
        llm_started = self.clock()
        first_token_at: float | None = None
        first_audio_at: float | None = None
        audio_chunks = 0
        audio_bytes = 0
        logger.info(
            "%s llm request turn=%s provider=%s model=%s endpoint=%s messages=%d",
            self._tag,
            self._label(generation),
            self.llm.name,
            self.settings.llm_model,
            self.settings.llm_base_url,
            len(messages),
        )

        async def produce() -> None:
            nonlocal first_token_at
            chunker = SentenceChunker()
            try:
                async for token in self.llm.stream(messages):
                    if generation != self._generation:
                        break
                    await self._consume_usage(
                        "llm",
                        chars=len(token),
                        tokens=(len(token) + 3) // 4,
                    )
                    if first_token_at is None:
                        first_token_at = self.clock()
                        turn["llm_first_token_ms"] = _ms(llm_started, first_token_at)
                        await self.transport.send(
                            {
                                "type": "turn.timing",
                                "turn_id": self._label(generation),
                                "stage": "llm_first_token",
                            }
                        )
                    tokens.append(token)
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
            nonlocal first_audio_at, audio_chunks, audio_bytes
            while True:
                sentence = await queue.get()
                if sentence is None:
                    break
                if generation != self._generation:
                    break
                logger.debug(
                    "%s tts sentence turn=%s text=%r",
                    self._tag,
                    self._label(generation),
                    sentence,
                )
                await self._consume_usage("tts", chars=len(sentence))
                tts_started = self.clock()
                sentence_text_sent = False
                async for chunk in self.tts.synthesize(sentence, voice=self._voice):
                    if generation != self._generation:
                        logger.info(
                            "%s dropping audio from cancelled turn=%s",
                            self._tag,
                            self._label(generation),
                        )
                        return
                    audio_chunks += 1
                    audio_bytes += len(chunk)
                    if first_audio_at is None:
                        first_audio_at = self.clock()
                        turn["tts_first_audio_ms"] = _ms(tts_started, first_audio_at)
                        turn["e2e_first_audio_ms"] = _ms(ts_end, first_audio_at)
                        logger.info(
                            "%s first audio to client turn=%s tts_ms=%.1f e2e_ms=%.1f",
                            self._tag,
                            self._label(generation),
                            turn["tts_first_audio_ms"],
                            turn["e2e_first_audio_ms"],
                        )
                        await self._set_state("speaking", generation)
                    event: dict[str, Any] = {
                        "type": "audio.chunk",
                        "turn_id": self._label(generation),
                        "data": base64.b64encode(chunk).decode("ascii"),
                        "sample_rate": self.tts.sample_rate,
                        "format": "pcm16",
                    }
                    if not sentence_text_sent:
                        # The browser reveals this sentence when this first
                        # chunk reaches the speakers, keeping transcript and
                        # voice on the same timeline even when TTS runs ahead.
                        event["text"] = sentence
                        sentence_text_sent = True
                    await self.transport.send(event)

        await self._gather(produce(), consume())

        if generation != self._generation:
            logger.info(
                "%s turn=%s cancelled before completion",
                self._tag,
                self._label(generation),
            )
            return

        full_text = "".join(tokens).strip()
        if full_text:
            self.session.add("assistant", full_text)

        turn["total_ms"] = _ms(ts_end, self.clock())
        self.metrics.record(turn)
        logger.info(
            "%s llm response turn=%s first_token_ms=%s chars=%d text=%r",
            self._tag,
            self._label(generation),
            turn.get("llm_first_token_ms"),
            len(full_text),
            _clip(full_text),
        )
        logger.info(
            "%s audio sent turn=%s chunks=%d bytes=%d total_ms=%.1f",
            self._tag,
            self._label(generation),
            audio_chunks,
            audio_bytes,
            turn["total_ms"],
        )

        await self.transport.send(
            {
                "type": "assistant.done",
                "turn_id": self._label(generation),
                "text": full_text,
            }
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

    async def _consume_usage(
        self,
        kind: str,
        *,
        chars: int = 0,
        tokens: int = 0,
    ) -> None:
        if self.usage_guard is None:
            return
        denied = await self.usage_guard(kind, chars, tokens)
        if denied:
            raise UsageLimitExceeded(denied)

    async def _fail(self, generation: int, stage: str, message: str) -> None:
        if generation != self._generation:
            logger.info(
                "%s dropping failure from stale turn=%s stage=%s",
                self._tag,
                self._label(generation),
                stage,
            )
            return
        logger.warning(
            "%s turn=%s failed stage=%s message=%s",
            self._tag,
            self._label(generation),
            stage,
            message,
        )
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
        await self.transport.send(
            {"type": "assistant.failed", "turn_id": self._label(generation)}
        )
        await self._set_state("listening", generation)

    # ------------------------------------------------------------ client input

    async def handle_client_metrics(
        self, turn_id: str, payload: dict[str, Any]
    ) -> None:
        allowed = {
            key: value
            for key, value in payload.items()
            if key in {"first_playback_ms", "barge_in_ms", "playback_ms"}
            and isinstance(value, (int, float))
        }
        if allowed:
            self.metrics.merge(turn_id, allowed)

    async def interrupt(
        self, reason: str = "manual", turn_id: str | None = None
    ) -> None:
        """Cancel the active assistant response.

        When ``turn_id`` is supplied (the browser's barge-in path), the
        cancellation only applies if that turn is still the active one. A late
        interrupt for an older turn can therefore never cancel a newer reply.
        """
        logger.info("%s interrupt reason=%s turn=%s", self._tag, reason, turn_id or "-")

        if turn_id is not None:
            cancelled = await self._cancel_turn(reason, expected_turn_id=turn_id)
            if cancelled is None:
                # The response already finished, or a newer turn is active.
                return
            # If the server VAD has already begun the next utterance, leave its
            # STT stream and pre-roll alone. The interrupt only targets the
            # response that was interrupted.
            if not self.vad.is_speech:
                self.vad.reset()
                await self.stt.cancel_utterance()
                self._stt_error = None
            await self._set_state("listening")
            return

        # Manual/legacy interrupt: stop whatever is running, including an STT
        # utterance that has not reached the LLM yet.
        await self._cancel_turn(reason)
        self._generation += 1
        self.vad.reset()
        await self.stt.cancel_utterance()
        self._stt_error = None
        await self._set_state("listening")

    async def _cancel_turn(
        self, reason: str, expected_turn_id: str | None = None
    ) -> str | None:
        """Cancel the active turn task and announce it exactly once.

        The generation counter advances before the task is cancelled, so even a
        provider that ignores ``CancelledError`` cannot emit more text or audio
        for the interrupted turn.
        """
        task = self._turn_task
        if task is None or task.done():
            return None
        turn_id = self._label(self._task_turn_id or 0)
        if expected_turn_id is not None and expected_turn_id != turn_id:
            logger.info(
                "%s ignoring stale interrupt turn=%s active=%s",
                self._tag,
                expected_turn_id,
                turn_id,
            )
            return None

        self._generation += 1
        self._turn_task = None
        self._task_turn_id = None
        task.cancel()
        task.add_done_callback(self._orphan_tasks.discard)
        self._orphan_tasks.add(task)
        logger.info(
            "%s cancelling turn=%s reason=%s",
            self._tag,
            turn_id,
            reason,
        )
        try:
            done, pending = await asyncio.wait({task}, timeout=_CANCEL_GRACE_S)
            if pending:
                logger.warning(
                    "%s turn=%s did not stop within %.0f ms; stale output is gated",
                    self._tag,
                    turn_id,
                    _CANCEL_GRACE_S * 1000,
                )
            for finished in done:
                if not finished.cancelled():
                    # Retrieve the exception so asyncio does not log it later.
                    finished.exception()
        except asyncio.CancelledError:
            raise

        await self.transport.send(
            {
                "type": "turn.cancelled",
                "turn_id": turn_id,
                "reason": reason,
            }
        )
        return turn_id

    # ------------------------------------------------------------------ utils

    async def _set_state(self, state: str, generation: int | None = None) -> None:
        if state == self._state:
            return
        self._state = state
        await self.transport.send(
            {
                "type": "state",
                "state": state,
                "turn_id": self._label(
                    generation if generation is not None else self._generation
                ),
            }
        )

    def _label(self, generation: int) -> str:
        return f"{self.session.session_id[:8]}-{generation}"

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        tasks: list[asyncio.Task[None]] = []
        if self._turn_task is not None and not self._turn_task.done():
            self._turn_task.cancel()
            tasks.append(self._turn_task)
        for task in list(self._orphan_tasks):
            if not task.done():
                task.cancel()
            tasks.append(task)
        if self._tts_prewarm_task is not None and not self._tts_prewarm_task.done():
            self._tts_prewarm_task.cancel()
            tasks.append(self._tts_prewarm_task)
        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                raise
        self._turn_task = None
        self._task_turn_id = None
        self._tts_prewarm_task = None
        self._orphan_tasks.clear()
        for provider in (self.stt, self.tts):
            try:
                await provider.close()
            except Exception:  # pragma: no cover - best effort cleanup
                logger.debug("Provider close failed", exc_info=True)


__all__ = ["VoicePipeline"]
