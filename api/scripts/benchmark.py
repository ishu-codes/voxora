"""Reproducible latency benchmark for a running Voxora backend.

It drives one WebSocket session per run, executes scripted turns, and reports
end-of-speech to first-audio latency plus interruption latency. Timings are
measured on the client from a monotonic clock, matching the PRD's requirement
to measure the full user-perceived path rather than summing stage p95s.

Usage
-----
    # zero-key stack (browser STT semantics, demo LLM, browser TTS)
    python -m scripts.benchmark --turns 10

    # replay a 16 kHz mono WAV through a server-side STT provider
    python -m scripts.benchmark --turns 5 --wav sample.wav

    # also measure barge-in -> first cancelled audio
    python -m scripts.benchmark --turns 5 --barge-in

    # compare against the server's own per-stage summary
    python -m scripts.benchmark --turns 10 --server-metrics
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import struct
import time
import wave
from dataclasses import dataclass, field
from typing import Any

import websockets

SAMPLE_RATE = 16_000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2
SILENCE_FRAMES = 40  # 800 ms, comfortably past the 650 ms default endpoint

PROMPTS = [
    "Explain what a database index does in two sentences.",
    "Give me one reason streaming speech synthesis reduces latency.",
    "What is voice activity detection used for?",
    "How does barge-in cancellation work?",
    "Summarise the pipeline in one short sentence.",
]


def tone_frame(amplitude: float = 0.35) -> bytes:
    value = int(amplitude * 32767)
    return struct.pack("<h", value) * FRAME_SAMPLES


def silence_frame() -> bytes:
    return b"\x00\x00" * FRAME_SAMPLES


def wav_frames(path: str) -> list[bytes]:
    with wave.open(path, "rb") as wav:
        if wav.getframerate() != SAMPLE_RATE or wav.getnchannels() != 1:
            raise SystemExit(
                f"{path} must be {SAMPLE_RATE} Hz mono; "
                f"got {wav.getframerate()} Hz / {wav.getnchannels()} channel(s)"
            )
        raw = wav.readframes(wav.getnframes())
    padded = raw + b"\x00" * ((-len(raw)) % FRAME_BYTES)
    return [padded[i : i + FRAME_BYTES] for i in range(0, len(padded), FRAME_BYTES)]


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    rank = (len(ordered) - 1) * p / 100
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 1)


@dataclass
class TurnResult:
    index: int
    first_audio_ms: float | None = None
    total_ms: float | None = None
    barge_in_ms: float | None = None
    error: str | None = None
    server_metrics: dict[str, Any] = field(default_factory=dict)


class BenchSession:
    def __init__(self, url: str, use_wav: list[bytes] | None) -> None:
        self.url = url
        self.use_wav = use_wav
        self.results: list[TurnResult] = []
        self._events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._ready: dict[str, Any] | None = None

    async def run(self, turns: int, barge_in: bool) -> None:
        async with websockets.connect(self.url, max_size=None) as socket:
            reader = asyncio.create_task(self._reader(socket))
            self._ready = await self._expect("ready")
            for index in range(turns):
                if barge_in and index == turns - 1:
                    await self._barge_in_turn(socket, index)
                else:
                    await self._normal_turn(socket, index)
            reader.cancel()

    async def _reader(self, socket: Any) -> None:
        try:
            async for raw in socket:
                if isinstance(raw, bytes):
                    continue
                await self._events.put(json.loads(raw))
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - connection teardown
            return

    async def _next(self, timeout: float) -> dict[str, Any]:
        return await asyncio.wait_for(self._events.get(), timeout=timeout)

    async def _expect(self, event_type: str, timeout: float = 20.0) -> dict[str, Any]:
        deadline = time.perf_counter() + timeout
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError(f"timed out waiting for {event_type}")
            event = await self._next(remaining)
            if event.get("type") == event_type:
                return event

    async def _send_speech(self, socket: Any, prompt: str, turn_index: int) -> None:
        frames = self.use_wav if self.use_wav else [tone_frame()] * 25
        for frame in frames:
            await socket.send(frame)
        if not self.use_wav:
            await socket.send(
                json.dumps({"type": "transcript", "text": PROMPTS[turn_index % len(PROMPTS)], "final": True})
            )

    async def _normal_turn(self, socket: Any, index: int) -> None:
        result = TurnResult(index=index)
        await self._send_speech(socket, PROMPTS[index % len(PROMPTS)], index)

        loop = asyncio.get_running_loop()
        for _ in range(SILENCE_FRAMES):
            await socket.send(silence_frame())
        speech_end = loop.time()

        while True:
            event = await self._next(timeout=30.0)
            kind = event.get("type")
            if kind in {"speak.chunk", "audio.chunk"} and result.first_audio_ms is None:
                result.first_audio_ms = round((loop.time() - speech_end) * 1000, 1)
            elif kind == "turn.metrics":
                # The backend emits assistant.done and then turn.metrics, so the
                # metrics event is the natural end of the turn.
                result.total_ms = round((loop.time() - speech_end) * 1000, 1)
                result.server_metrics = event.get("metrics", {})
                break
            elif kind == "assistant.failed":
                result.error = "assistant failed"
                break
            elif kind == "turn.empty":
                result.error = "empty transcript"
                break
            elif kind == "error":
                result.error = f"{event.get('stage')}: {event.get('message')}"
                break

        self.results.append(result)
        print(
            f"turn {index + 1:>2}  first_audio={result.first_audio_ms} ms  "
            f"total={result.total_ms} ms  error={result.error}"
        )

    async def _barge_in_turn(self, socket: Any, index: int) -> None:
        """Start a turn, then interrupt it once audio begins."""
        result = TurnResult(index=index)
        await self._send_speech(socket, PROMPTS[index % len(PROMPTS)], index + 1)
        loop = asyncio.get_running_loop()
        for _ in range(SILENCE_FRAMES):
            await socket.send(silence_frame())

        while True:
            event = await self._next(timeout=30.0)
            if event.get("type") in {"speak.chunk", "audio.chunk", "assistant.delta"}:
                break
            if event.get("type") in {"assistant.done", "assistant.failed"}:
                result.error = "turn finished before barge-in"
                self.results.append(result)
                return

        onset = loop.time()
        for _ in range(10):
            await socket.send(tone_frame(0.5))
        while True:
            event = await self._next(timeout=10.0)
            if event.get("type") == "turn.cancelled":
                result.barge_in_ms = round((loop.time() - onset) * 1000, 1)
                break
            if event.get("type") == "error":
                result.error = event.get("message")
                break
        self.results.append(result)
        print(f"turn {index + 1:>2}  barge_in={result.barge_in_ms} ms  error={result.error}")


def summarise(results: list[TurnResult]) -> dict[str, Any]:
    first_audio = [r.first_audio_ms for r in results if r.first_audio_ms is not None]
    barge_in = [r.barge_in_ms for r in results if r.barge_in_ms is not None]
    total = [r.total_ms for r in results if r.total_ms is not None]
    errors = [r.error for r in results if r.error]
    return {
        "turns": len(results),
        "errors": len(errors),
        "success_rate": round(1 - len(errors) / len(results), 3) if results else 0,
        "first_audio_ms": {
            "count": len(first_audio),
            "mean": round(statistics.fmean(first_audio), 1) if first_audio else None,
            "p50": percentile(first_audio, 50),
            "p95": percentile(first_audio, 95),
            "p99": percentile(first_audio, 99),
        },
        "total_ms": {
            "p50": percentile(total, 50),
            "p95": percentile(total, 95),
        },
        "barge_in_ms": {
            "count": len(barge_in),
            "p50": percentile(barge_in, 50),
            "p95": percentile(barge_in, 95),
        },
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Voxora latency benchmark")
    parser.add_argument("--url", default="ws://127.0.0.1:8000/api/v1/voice/ws")
    parser.add_argument("--turns", type=int, default=5)
    parser.add_argument("--wav", help="16 kHz mono WAV to replay instead of a synthetic tone")
    parser.add_argument("--barge-in", action="store_true", help="measure interruption latency on turn 1")
    parser.add_argument("--server-metrics", action="store_true", help="fetch /api/v1/voice/metrics after the run")
    args = parser.parse_args()

    use_wav = wav_frames(args.wav) if args.wav else None
    session = BenchSession(args.url, use_wav)
    await session.run(args.turns, args.barge_in)

    report = summarise(session.results)
    print(json.dumps(report, indent=2))

    if args.server_metrics:
        import httpx

        base = args.url.replace("wss://", "https://").replace("ws://", "http://")
        base = base[: base.index("/api/")]
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base}/api/v1/voice/metrics")
            print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
