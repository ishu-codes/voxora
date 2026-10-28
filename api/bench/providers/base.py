"""Provider contracts and timing records for benchmark runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class BenchmarkProviderError(RuntimeError):
    """A provider failure that should be included in results, not hidden."""


@dataclass
class STTResult:
    text: str
    t_request_sent: float
    t_first_partial: float | None
    t_final: float
    provider: str
    model: str
    mode: str
    t_audio_end: float | None = None


@dataclass
class TTSResult:
    audio_bytes: bytes
    t_request_sent: float
    t_first_audio_byte: float
    t_done: float


class STTProvider(Protocol):
    name: str
    model: str
    mode: str

    async def transcribe_file(
        self,
        wav_path: str,
        language_hint: str | None,
    ) -> STTResult: ...

    async def close(self) -> None: ...


class TTSProvider(Protocol):
    name: str
    model: str

    async def synthesize(self, text: str, language: str) -> TTSResult: ...

    async def close(self) -> None: ...


__all__ = [
    "BenchmarkProviderError",
    "STTProvider",
    "STTResult",
    "TTSProvider",
    "TTSResult",
]
