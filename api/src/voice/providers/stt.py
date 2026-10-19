"""Speech-to-text adapters."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import AsyncIterator

import httpx

from ..audio import pcm16_to_wav
from ..config import Settings
from .base import ProviderError

logger = logging.getLogger(__name__)


class BrowserSTT:
    """The browser's own streaming recogniser supplies final transcripts.

    Audio still flows through the backend for VAD and barge-in, but no audio is
    uploaded to a third party for transcription.  This is the zero-key default
    when no server-side model is configured.
    """

    name = "browser"
    supports_partials = True

    async def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        return ""

    async def close(self) -> None:
        return None


class OpenAICompatibleSTT:
    """Batch transcription through an OpenAI-compatible ``/audio/transcriptions``."""

    name = "openai"
    supports_partials = False

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.stt_base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Authorization": f"Bearer {settings.key_for('stt')}"},
        )

    async def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        if not pcm:
            return ""
        wav = pcm16_to_wav(pcm, sample_rate)
        data: dict[str, str] = {"model": self._settings.stt_model}
        if self._settings.stt_language:
            data["language"] = self._settings.stt_language
        files = {"file": ("utterance.wav", wav, "audio/wav")}
        try:
            response = await self._client.post("/audio/transcriptions", data=data, files=files)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise ProviderError("stt", f"Transcription failed ({exc.response.status_code}): {detail}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("stt", f"Transcription request failed: {exc}") from exc
        payload = response.json()
        text = str(payload.get("text", "")).strip()
        return text

    async def close(self) -> None:
        await self._client.aclose()


class FasterWhisperSTT:
    """Local transcription with faster-whisper when the optional package exists."""

    name = "faster-whisper"
    supports_partials = False

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        self._lock = asyncio.Lock()

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]

            self._model = WhisperModel(
                self._settings.whisper_model,
                device=self._settings.whisper_device,
                compute_type=self._settings.whisper_compute_type,
            )
        return self._model

    def _transcribe_sync(self, pcm: bytes, sample_rate: int) -> str:
        model = self._load()
        wav = io.BytesIO(pcm16_to_wav(pcm, sample_rate))
        segments, _info = model.transcribe(
            wav,
            language=self._settings.stt_language or None,
            vad_filter=False,
            beam_size=1,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    async def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        async with self._lock:
            try:
                return await asyncio.to_thread(self._transcribe_sync, pcm, sample_rate)
            except Exception as exc:  # model load or inference failure
                raise ProviderError("stt", f"Local transcription failed: {exc}") from exc

    async def close(self) -> None:
        self._model = None


def build_stt(settings: Settings) -> tuple[BrowserSTT | OpenAICompatibleSTT | FasterWhisperSTT, str]:
    """Return the configured STT adapter and the reason it was selected."""
    choice = settings.stt_provider
    if choice == "browser":
        return BrowserSTT(), "configured"
    if choice in {"openai", "openai-compatible", "groq"}:
        return OpenAICompatibleSTT(settings), "configured"
    if choice in {"faster-whisper", "faster_whisper", "whisper", "local"}:
        return FasterWhisperSTT(settings), "configured"

    # auto: prefer a hosted key, then a locally installed model, then browser.
    if settings.key_for("stt"):
        return OpenAICompatibleSTT(settings), "auto: API key present"
    try:
        import faster_whisper  # type: ignore[import-not-found]  # noqa: F401

        return FasterWhisperSTT(settings), "auto: faster-whisper installed"
    except Exception:
        return BrowserSTT(), "auto: no server STT available, using browser recognition"


__all__ = ["BrowserSTT", "OpenAICompatibleSTT", "FasterWhisperSTT", "build_stt"]
