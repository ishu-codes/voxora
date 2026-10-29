"""Audio conversion and validation shared by every STT provider."""

from __future__ import annotations

import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from bench.providers.base import BenchmarkProviderError


@dataclass(frozen=True)
class ConvertedAudio:
    pcm: bytes
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    duration_s: float


def wav_properties(path: str | Path) -> tuple[int, int, int, int]:
    """Return sample rate, channels, sample width, and frame count."""
    try:
        with wave.open(str(path), "rb") as wav:
            return (
                wav.getframerate(),
                wav.getnchannels(),
                wav.getsampwidth(),
                wav.getnframes(),
            )
    except (OSError, wave.Error) as exc:
        raise BenchmarkProviderError(f"Could not read WAV file {path}: {exc}") from exc


def convert_to_pcm16_mono(
    source: str | Path,
    sample_rate_hz: int,
) -> ConvertedAudio:
    """Convert any ffmpeg-readable input to the exact declared PCM format."""
    source = Path(source)
    if not source.exists():
        raise BenchmarkProviderError(f"Audio file does not exist: {source}")

    with tempfile.TemporaryDirectory(prefix="voxora-bench-audio-") as temp_dir:
        converted_path = Path(temp_dir) / "converted.wav"
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            str(sample_rate_hz),
            "-c:a",
            "pcm_s16le",
            str(converted_path),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise BenchmarkProviderError(
                "ffmpeg is required to normalize benchmark audio."
            ) from exc
        except subprocess.SubprocessError as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise BenchmarkProviderError(
                f"Could not convert {source} with ffmpeg: {detail.strip()}"
            ) from exc

        rate, channels, width, frames = wav_properties(converted_path)
        if rate != sample_rate_hz or channels != 1 or width != 2:
            raise BenchmarkProviderError(
                "Converted audio format mismatch: "
                f"got {rate} Hz, {channels} channel(s), {width * 8}-bit; "
                f"expected {sample_rate_hz} Hz, mono, 16-bit."
            )
        with wave.open(str(converted_path), "rb") as wav:
            raw = wav.readframes(wav.getnframes())
    return ConvertedAudio(
        pcm=raw,
        sample_rate_hz=rate,
        channels=channels,
        sample_width_bytes=width,
        duration_s=frames / rate if rate else 0.0,
    )


__all__ = ["ConvertedAudio", "convert_to_pcm16_mono", "wav_properties"]
