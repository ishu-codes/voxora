"""Small audio helpers built on the standard library."""

from __future__ import annotations

import math

from ..core.config import BYTES_PER_SAMPLE


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


__all__ = ["pcm16_rms"]
