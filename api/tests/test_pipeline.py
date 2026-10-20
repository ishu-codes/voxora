import asyncio
import base64
import struct
from typing import AsyncIterator

import pytest

from src.voice.config import FRAME_BYTES, Settings
from src.voice.metrics import MetricsRegistry
from src.voice.pipeline import VoicePipeline
from src.voice.transport import CollectingTransport
from src.voice.vad import EnergyVAD


def _frame(amplitude: float) -> bytes:
    value = int(amplitude * 32767)
    return struct.pack("<h", value) * (FRAME_BYTES // 2)


class FakeSTT:
    """In-memory stand-in for the Sarvam streaming adapter."""

    name = "fake"
    supports_partials = True

    def __init__(self, text: str = "what is latency", partials: tuple[str, ...] = ()) -> None:
        self.text = text
        self.partials = partials
        self.calls = 0
        self.frames = 0
        self.begun = 0
        self.cancelled = 0
        self._on_partial = None

    async def begin_utterance(self, on_partial=None) -> None:
        self.begun += 1
        self._on_partial = on_partial
        for partial in self.partials:
            if on_partial is not None:
                await on_partial(partial)

    async def push_audio(self, pcm: bytes) -> None:
        self.frames += len(pcm)

    async def end_utterance(self) -> str:
        self.calls += 1
        return self.text

    async def cancel_utterance(self) -> None:
        self.cancelled += 1

    async def close(self) -> None:
        return None


class FakeLLM:
    name = "fake-llm"
    streaming = True

    def __init__(self, tokens: list[str], delay: float = 0.0) -> None:
        self.tokens = tokens
        self.delay = delay

    async def _stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        for token in self.tokens:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield token

    def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        return self._stream(messages)

    async def close(self) -> None:
        return None


class FakeAudioTTS:
    name = "fake-tts"
    kind = "audio"
    sample_rate = 24_000

    def __init__(self, chunks: int = 2) -> None:
        self.chunks = chunks
        self.voices: list[str | None] = []

    async def _stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        self.voices.append(voice)
        for _ in range(self.chunks):
            yield b"\x00\x01" * 128

    def synthesize(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        return self._stream(text, voice)

    async def close(self) -> None:
        return None


class SlowAudioTTS(FakeAudioTTS):
    """Emits audio over time so a turn can be interrupted mid-synthesis."""

    async def _stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        self.voices.append(voice)
        for _ in range(6):
            yield b"\x00\x01" * 128
            await asyncio.sleep(0.05)


def _settings(**overrides) -> Settings:
    base = dict(
        vad_threshold=0.02,
        vad_start_frames=2,
        vad_end_silence_ms=40,
        vad_pre_roll_ms=40,
        max_history_messages=8,
    )
    base.update(overrides)
    return Settings(**base)


def _pipeline(stt, llm, tts, settings=None, metrics=None, turn_limit=None):
    settings = settings or _settings()
    vad = EnergyVAD(
        threshold=settings.vad_threshold,
        start_frames=settings.vad_start_frames,
        end_silence_ms=settings.vad_end_silence_ms,
        pre_roll_ms=settings.vad_pre_roll_ms,
        max_utterance_ms=settings.vad_max_utterance_ms,
    )
    transport = CollectingTransport()
    pipeline = VoicePipeline(
        transport,
        settings,
        stt,
        llm,
        tts,
        vad=vad,
        metrics=metrics or MetricsRegistry(),
        turn_limit=turn_limit,
    )
    return pipeline, transport


async def _speak(pipeline: VoicePipeline, frames: int = 2) -> None:
    for _ in range(frames):
        await pipeline.feed_audio(_frame(0.3))


async def _silence(pipeline: VoicePipeline, frames: int) -> None:
    for _ in range(frames):
        await pipeline.feed_audio(_frame(0.0))


async def _await_turn(pipeline: VoicePipeline, timeout: float = 3.0) -> None:
    task = pipeline._turn_task
    assert task is not None
    await asyncio.wait_for(task, timeout)


async def test_full_turn_streams_partials_and_audio():
    stt = FakeSTT("what is latency", partials=("what is", "what is latency"))
    llm = FakeLLM(["Latency ", "is the ", "delay ", "between ", "events."])
    pipeline, transport = _pipeline(stt, llm, FakeAudioTTS(2))

    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    assert stt.begun == 1
    assert stt.calls == 1
    assert stt.frames > 0, "utterance audio should reach the streaming STT"
    partials = transport.of_type("transcript.partial")
    assert [event["text"] for event in partials] == ["what is", "what is latency"]
    final = transport.of_type("transcript.final")
    assert final and final[0]["text"] == "what is latency"
    assert transport.of_type("assistant.delta")
    assert len(transport.of_type("audio.chunk")) == 2
    assert transport.of_type("assistant.done")[0]["text"].strip() == (
        "Latency is the delay between events."
    )
    metrics = transport.of_type("turn.metrics")
    assert metrics and metrics[0]["metrics"]["e2e_first_audio_ms"] is not None
    states = [event["state"] for event in transport.of_type("state")]
    assert states == ["listening", "thinking", "speaking", "listening"]
    assert pipeline.session.history
    await pipeline.close()


async def test_audio_chunks_are_base64_pcm16_at_provider_rate():
    pipeline, transport = _pipeline(
        FakeSTT(), FakeLLM(["A longer answer for playback."]), FakeAudioTTS(2)
    )
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    chunks = transport.of_type("audio.chunk")
    assert len(chunks) == 2
    assert base64.b64decode(chunks[0]["data"])
    assert chunks[0]["sample_rate"] == 24_000
    assert chunks[0]["format"] == "pcm16"
    await pipeline.close()


async def test_selected_voice_is_used_for_synthesis():
    tts = FakeAudioTTS(1)
    pipeline, _transport = _pipeline(FakeSTT(), FakeLLM(["Voice test."]), tts)
    pipeline.set_voice("ritu")

    assert pipeline.ready_event()["tts"]["voice"] == "ritu"

    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    assert tts.voices == ["ritu"]
    await pipeline.close()


async def test_empty_transcript_ends_turn_cleanly():
    pipeline, transport = _pipeline(FakeSTT(""), FakeLLM(["unused"]), FakeAudioTTS())
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    assert transport.of_type("turn.empty")
    assert transport.of_type("assistant.done") == []
    assert pipeline.session.history == []
    await pipeline.close()


async def test_barge_in_cancels_generation_and_marks_latest_turn():
    llm = FakeLLM(["one ", "two ", "three ", "four ", "five."], delay=0.05)
    pipeline, transport = _pipeline(FakeSTT(), llm, FakeAudioTTS())

    await _speak(pipeline)
    await _silence(pipeline, 3)
    await asyncio.sleep(0.12)  # let generation begin

    # User speaks again: VAD fires speech_start, which must cancel the turn.
    await _speak(pipeline)
    await asyncio.sleep(0.05)

    cancelled = transport.of_type("turn.cancelled")
    assert cancelled and cancelled[0]["reason"] == "barge_in"
    assert transport.of_type("assistant.done") == []

    # The interrupted turn's task must be finished (nothing left running).
    await _silence(pipeline, 3)
    await _await_turn(pipeline)
    first_turn_id = cancelled[0]["turn_id"]
    deltas = [
        event
        for event in transport.of_type("assistant.delta")
        if event["turn_id"] == first_turn_id
    ]
    assert deltas, "the partial answer should have streamed before cancellation"
    await pipeline.close()


async def test_manual_interrupt_stops_turn_and_stt_utterance():
    llm = FakeLLM(["a ", "b ", "c"], delay=0.1)
    stt = FakeSTT()
    pipeline, transport = _pipeline(stt, llm, FakeAudioTTS())
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await asyncio.sleep(0.05)

    await pipeline.interrupt("manual")
    cancelled = transport.of_type("turn.cancelled")
    assert cancelled and cancelled[0]["reason"] == "manual"
    assert stt.cancelled == 1
    await pipeline.close()


async def test_provider_error_surfaces_and_recovers():
    class BrokenLLM(FakeLLM):
        async def _stream(self, messages):
            from src.voice.providers.base import ProviderError

            raise ProviderError("llm", "boom")
            yield  # pragma: no cover

    pipeline, transport = _pipeline(FakeSTT(), BrokenLLM([]), FakeAudioTTS())
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    errors = transport.of_type("error")
    assert errors and errors[0]["stage"] == "llm"
    assert transport.of_type("assistant.failed")
    assert transport.of_type("state")[-1]["state"] == "listening"
    await pipeline.close()


async def test_stt_failure_surfaces_at_turn_end():
    class BrokenSTT(FakeSTT):
        async def begin_utterance(self, on_partial=None) -> None:
            from src.voice.providers.base import ProviderError

            raise ProviderError("stt", "sarvam down")

    pipeline, transport = _pipeline(BrokenSTT(), FakeLLM(["unused"]), FakeAudioTTS())
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    errors = [event for event in transport.of_type("error") if event["stage"] == "stt"]
    assert errors and errors[0]["message"] == "sarvam down"
    assert transport.of_type("assistant.failed")
    assert transport.of_type("state")[-1]["state"] == "listening"
    await pipeline.close()


async def test_client_metrics_are_merged_for_turn():
    metrics = MetricsRegistry()
    pipeline, transport = _pipeline(
        FakeSTT(), FakeLLM(["hello."]), FakeAudioTTS(), metrics=metrics
    )
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    turn_id = transport.of_type("assistant.done")[0]["turn_id"]
    await pipeline.handle_client_metrics(turn_id, {"first_playback_ms": 512.5, "ignored": "x"})
    summary = metrics.summary()
    assert summary["stages"]["first_playback_ms"]["p50"] == 512.5
    await pipeline.close()


async def test_no_stale_audio_after_barge_in():
    """A cancelled turn must never emit more audio after cancellation."""
    llm = FakeLLM(["First sentence to speak. ", "Second sentence continues. "])
    pipeline, transport = _pipeline(FakeSTT(), llm, SlowAudioTTS())

    await _speak(pipeline)
    await _silence(pipeline, 3)

    for _ in range(300):
        if transport.of_type("audio.chunk"):
            break
        await asyncio.sleep(0.01)

    chunks = transport.of_type("audio.chunk")
    assert chunks, "expected the turn to start streaming audio"
    cancelled_turn = chunks[0]["turn_id"]
    before = len(chunks)

    # Barge in while the first turn is still synthesising.
    await _speak(pipeline)
    await asyncio.sleep(0.5)

    assert transport.of_type("turn.cancelled"), "barge-in should cancel the turn"
    stale = [
        event
        for event in transport.of_type("audio.chunk")
        if event["turn_id"] == cancelled_turn
    ]
    assert len(stale) == before, "no stale audio chunks may follow cancellation"

    await _silence(pipeline, 3)
    await _await_turn(pipeline)
    await pipeline.close()


async def test_platform_turn_limit_blocks_extra_turns():
    pipeline, transport = _pipeline(
        FakeSTT("first question"),
        FakeLLM(["first answer."]),
        FakeAudioTTS(1),
        turn_limit=1,
    )

    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)
    assert pipeline.session.turn_count == 1

    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    quota = [event for event in transport.of_type("error") if event["stage"] == "quota"]
    assert quota and quota[0]["recoverable"] is False
    assert pipeline.session.turn_count == 1
    await pipeline.close()
