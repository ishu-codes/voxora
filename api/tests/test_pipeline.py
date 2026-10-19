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
    name = "fake"
    supports_partials = False

    def __init__(self, text: str = "what is latency") -> None:
        self.text = text
        self.calls = 0

    async def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        self.calls += 1
        return self.text

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


class FakeBrowserTTS:
    name = "browser"
    kind = "browser"
    sample_rate = 0

    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        raise AssertionError("browser TTS must not be asked for audio")

    async def close(self) -> None:
        return None


class FakeAudioTTS:
    name = "fake-tts"
    kind = "audio"
    sample_rate = 24_000

    def __init__(self, chunks: int = 2) -> None:
        self.chunks = chunks

    async def _stream(self, text: str) -> AsyncIterator[bytes]:
        for _ in range(self.chunks):
            yield b"\x00\x01" * 128

    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        return self._stream(text)

    async def close(self) -> None:
        return None


class SlowAudioTTS:
    """Emits audio over time so a turn can be interrupted mid-synthesis."""

    name = "slow-tts"
    kind = "audio"
    sample_rate = 24_000

    async def _stream(self, text: str) -> AsyncIterator[bytes]:
        for _ in range(6):
            yield b"\x00\x01" * 128
            await asyncio.sleep(0.05)

    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        return self._stream(text)

    async def close(self) -> None:
        return None


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


def _pipeline(stt, llm, tts, settings=None, metrics=None):
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
        transport, settings, stt, llm, tts, vad=vad, metrics=metrics or MetricsRegistry()
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


async def test_full_turn_uses_all_stages():
    stt = FakeSTT("what is latency")
    llm = FakeLLM(["Latency ", "is the ", "delay ", "between ", "events."])
    pipeline, transport = _pipeline(stt, llm, FakeBrowserTTS())

    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    assert stt.calls == 1
    final = transport.of_type("transcript.final")
    assert final and final[0]["text"] == "what is latency"
    assert transport.of_type("assistant.delta")
    assert transport.of_type("speak.chunk")
    assert transport.of_type("assistant.done")[0]["text"].strip() == (
        "Latency is the delay between events."
    )
    metrics = transport.of_type("turn.metrics")
    assert metrics and metrics[0]["metrics"]["e2e_first_audio_ms"] is not None
    states = [event["state"] for event in transport.of_type("state")]
    assert states == ["listening", "thinking", "speaking", "listening"]
    assert pipeline.session.history
    await pipeline.close()


async def test_audio_provider_emits_base64_pcm_chunks():
    pipeline, transport = _pipeline(FakeSTT(), FakeLLM(["A longer answer for playback."]), FakeAudioTTS(2))
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    chunks = transport.of_type("audio.chunk")
    assert len(chunks) == 2
    assert base64.b64decode(chunks[0]["data"])
    assert chunks[0]["sample_rate"] == 24_000
    await pipeline.close()


async def test_empty_transcript_ends_turn_cleanly():
    pipeline, transport = _pipeline(FakeSTT(""), FakeLLM(["unused"]), FakeBrowserTTS())
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    assert transport.of_type("turn.empty")
    assert transport.of_type("assistant.done") == []
    assert pipeline.session.history == []
    await pipeline.close()


async def test_barge_in_cancels_generation_and_marks_latest_turn():
    llm = FakeLLM(["one ", "two ", "three ", "four ", "five."], delay=0.05)
    pipeline, transport = _pipeline(FakeSTT(), llm, FakeBrowserTTS())

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
    deltas = [event for event in transport.of_type("assistant.delta") if event["turn_id"] == first_turn_id]
    assert deltas, "the partial answer should have streamed before cancellation"
    await pipeline.close()


async def test_manual_interrupt_stops_turn():
    llm = FakeLLM(["a ", "b ", "c"], delay=0.1)
    pipeline, transport = _pipeline(FakeSTT(), llm, FakeBrowserTTS())
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await asyncio.sleep(0.05)

    await pipeline.interrupt("manual")
    cancelled = transport.of_type("turn.cancelled")
    assert cancelled and cancelled[0]["reason"] == "manual"
    await pipeline.close()


async def test_provider_error_surfaces_and_recovers():
    class BrokenLLM(FakeLLM):
        async def _stream(self, messages):
            from src.voice.providers.base import ProviderError

            raise ProviderError("llm", "boom")
            yield  # pragma: no cover

    pipeline, transport = _pipeline(FakeSTT(), BrokenLLM([]), FakeBrowserTTS())
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)

    errors = transport.of_type("error")
    assert errors and errors[0]["stage"] == "llm"
    assert transport.of_type("assistant.failed")
    assert transport.of_type("state")[-1]["state"] == "listening"
    await pipeline.close()


async def test_client_metrics_are_merged_for_turn():
    metrics = MetricsRegistry()
    pipeline, transport = _pipeline(FakeSTT(), FakeLLM(["hello."]), FakeBrowserTTS(), metrics=metrics)
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


async def test_browser_stt_waits_for_client_transcript():
    from src.voice.providers.stt import BrowserSTT

    pipeline, transport = _pipeline(BrowserSTT(), FakeLLM(["Hi."]), FakeBrowserTTS())

    async def deliver():
        await asyncio.sleep(0.05)
        await pipeline.handle_browser_transcript("hello from the browser", final=True)

    deliver_task = asyncio.create_task(deliver())
    await _speak(pipeline)
    await _silence(pipeline, 3)
    await _await_turn(pipeline)
    await deliver_task

    assert transport.of_type("transcript.final")[0]["text"] == "hello from the browser"
    assert pipeline.session.history[0].content == "hello from the browser"
    await pipeline.close()
