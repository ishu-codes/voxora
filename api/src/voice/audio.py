"""Small audio helpers built on the standard library."""

from __future__ import annotations

import io
import math
import struct
import wave

from .config import BYTES_PER_SAMPLE


def pcm16_rms(pcm: bytes) -> float:
    """Return the root-mean-square amplitude of signed 16-bit PCM, scaled 0..1."""
    sample_count = len(pcm) // BYTES_PER_SAMPLE
    if sample_count == 0:
        return 0.0
    # ``memoryview.cast`` is cheap and avoids materialising a Python list.
    samples = memoryview(pcm)[: sample_count * BYTES_PER_SAMPLE].cast("h")
    total = 0
    for sample in samples:
        total += sample * sample
    mean_square = total / sample_count
    return math.sqrt(mean_square) / 32768.0


def pcm16_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    """Wrap raw little-endian mono PCM in a WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(BYTES_PER_SAMPLE)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def pcm_duration_ms(pcm: bytes, sample_rate: int) -> float:
    if sample_rate <= 0:
        return 0.0
    return len(pcm) / BYTES_PER_SAMPLE / sample_rate * 1000.0


def pcm16_peak(pcm: bytes) -> float:
    sample_count = len(pcm) // BYTES_PER_SAMPLE
    if sample_count == 0:
        return 0.0
    samples = memoryview(pcm)[: sample_count * BYTES_PER_SAMPLE].cast("h")
    return max(abs(sample) for sample in samples) / 32768.0


def silence_pcm(duration_ms: int, sample_rate: int) -> bytes:
    frames = int(sample_rate * duration_ms / 1000)
    return struct.pack("<h", 0) * frames
