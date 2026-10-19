"""Text-to-speech adapters.

The default ``browser`` adapter ships sentence chunks to the Web Speech API,
which needs no key and works offline.  The hosted adapter requests raw PCM so
the browser can enqueue it without an MP3 decoder round-trip.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

import httpx

from ..config import Settings
from .base import ProviderError

logger = logging.getLogger(__name__)


class BrowserTTS:
    kind = "browser"  # the pipeline special-cases this kind and emits text
    name = "browser"
    sample_rate = 0

    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        raise RuntimeError("BrowserTTS does not produce audio on the server")

    async def close(self) -> None:
        return None

    @property
    def is_browser(self) -> bool:
        return True


class OpenAITTS:
    kind = "audio"
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.sample_rate = settings.tts_sample_rate
        self._client = httpx.AsyncClient(
            base_url=settings.tts_base_url,
            timeout=httpx.Timeout(settings.tts_timeout_s, connect=10.0),
            headers={"Authorization": f"Bearer {settings.key_for('tts')}"},
        )

    async def _stream(self, text: str) -> AsyncIterator[bytes]:
        payload = {
            "model": self._settings.tts_model,
            "voice": self._settings.tts_voice,
            "input": text,
            "response_format": "pcm",
            "speed": self._settings.tts_speed,
        }
        try:
            async with self._client.stream("POST", "/audio/speech", json=payload) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")[:400]
                    raise ProviderError(
                        "tts", f"Speech synthesis error ({response.status_code}): {body}"
                    )
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if chunk:
                        yield chunk
        except httpx.HTTPError as exc:
            raise ProviderError("tts", f"Speech synthesis request failed: {exc}") from exc

    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        return self._stream(text)

    async def close(self) -> None:
        await self._client.aclose()


def build_tts(settings: Settings) -> tuple[BrowserTTS | OpenAITTS, str]:
    choice = settings.tts_provider
    if choice == "browser":
        return BrowserTTS(), "configured"
    if choice in {"openai", "openai-compatible"}:
        return OpenAITTS(settings), "configured"
    if settings.key_for("tts"):
        return OpenAITTS(settings), "auto: API key present"
    return BrowserTTS(), "auto: no TTS key, using browser speech"


__all__ = ["BrowserTTS", "OpenAITTS", "build_tts"]
