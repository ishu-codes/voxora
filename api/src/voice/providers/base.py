"""Provider contracts for speech-to-text, language generation and synthesis.

Speech adapters are stateful: one instance belongs to one WebSocket session so
it can hold a persistent Sarvam streaming connection. The language-model
adapter is stateless and may be shared across sessions.
"""

from __future__ import annotations

from typing import AsyncIterator, Awaitable, Callable, Literal, Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """A recoverable upstream failure that should surface to the browser."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


def provider_http_error(stage: str, label: str, status: int, body: str) -> ProviderError:
    """Build a safe provider error without echoing credentials.

    Provider error bodies can include masked API keys and request details, so
    authentication failures always get a generic message. Other failures keep a
    short, whitespace-collapsed excerpt to make configuration issues debuggable.
    """
    if status in {401, 403}:
        return ProviderError(stage, f"{label} authentication failed. Check the provider API key.")
    if status == 429:
        return ProviderError(stage, f"{label} rate limit reached. Try again in a moment.")
    snippet = " ".join(body.split())[:200]
    return ProviderError(stage, f"{label} failed ({status}): {snippet}")


PartialCallback = Callable[[str], Awaitable[None]]


@runtime_checkable
class STTProvider(Protocol):
    """Streaming speech-to-text.

    Audio frames are pushed as they arrive so the provider can transcribe while
    the user is still speaking. ``end_utterance`` finalises the turn and
    returns the transcript.
    """

    name: str
    supports_partials: bool

    async def begin_utterance(self, on_partial: PartialCallback | None = None) -> None: ...

    async def push_audio(self, pcm: bytes) -> None: ...

    async def end_utterance(self) -> str: ...

    async def cancel_utterance(self) -> None: ...

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
    kind: Literal["audio"]
    sample_rate: int

    def synthesize(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]: ...

    async def close(self) -> None: ...


__all__ = [
    "ProviderError",
    "provider_http_error",
    "PartialCallback",
    "STTProvider",
    "LLMProvider",
    "TTSProvider",
]
