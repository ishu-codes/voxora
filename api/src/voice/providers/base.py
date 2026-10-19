"""Provider contracts for speech-to-text, language generation and synthesis.

Adapters must state whether they genuinely stream.  A provider that needs the
whole utterance (for example a batch Whisper endpoint) returns ``False`` from
``supports_partials`` rather than pretending otherwise.
"""

from __future__ import annotations

from typing import AsyncIterator, Literal, Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """A recoverable upstream failure that should surface to the browser."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


@runtime_checkable
class STTProvider(Protocol):
    name: str
    supports_partials: bool

    async def transcribe(self, pcm: bytes, sample_rate: int) -> str: ...

    async def close(self) -> None: ...


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    streaming: bool

    def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]: ...

    async def close(self) -> None: ...


@runtime_checkable
class TTSProvider(Protocol):
    name: str
    kind: Literal["audio", "browser"]
    sample_rate: int

    def synthesize(self, text: str) -> AsyncIterator[bytes]: ...

    async def close(self) -> None: ...


__all__ = [
    "ProviderError",
    "STTProvider",
    "LLMProvider",
    "TTSProvider",
]
