"""Gnani Timbre v2.5 adapter for the TTS benchmark."""

from __future__ import annotations

import time

from bench.core.config import BenchmarkConfig
from bench.providers.base import BenchmarkProviderError, TTSResult
from src.voice.core.config import Settings
from src.voice.providers.gnani_tts import GnaniTTS as GnaniRealtimeTTS

_LANGUAGE = {
    "en": ("en-IN", "Kaveri"),
    "hi": ("hi-IN", "Chitra"),
    "hinglish": ("hi-en", "Poorvi"),
}


class GnaniTTS:
    name = "gnani-timbre"

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self.model = str(config.gnani["tts_model"])

    def _adapter(self, language: str, voice: str) -> GnaniRealtimeTTS:
        settings = Settings(
            gnani_api_key=self.config.gnani_api_key,
            gnani_tts_url=str(self.config.gnani["tts_url"]),
            gnani_tts_model=self.model,
            gnani_tts_voice=voice,
            gnani_tts_language=language,
            tts_sample_rate=int(self.config.tts["sample_rate_hz"]),
            tts_speed=float(self.config.gnani["tts_speed"]),
            tts_timeout_s=float(self.config.gnani["timeout_s"]),
            provider_retry_attempts=self.config.retry_attempts,
            provider_retry_base_ms=int(self.config.retry_base_delay * 1000),
        )
        return GnaniRealtimeTTS(settings, "benchmark-tts")

    async def synthesize(self, text: str, language: str) -> TTSResult:
        selected = _LANGUAGE.get(language)
        if selected is None:
            raise BenchmarkProviderError(
                f"Unsupported Gnani TTS language {language!r}."
        )
        language_code, voice = selected
        adapter = self._adapter(language_code, voice)
        try:
            # Prewarm outside the timer, then use a fresh socket so a late
            # frame from a previous synthesis cannot become this result.
            await adapter.prepare(voice)
            request_sent = time.perf_counter()
            first_audio: float | None = None
            audio = bytearray()
            async for chunk in adapter.synthesize(text, voice):
                if first_audio is None:
                    first_audio = time.perf_counter()
                audio.extend(chunk)
        except Exception as exc:
            if isinstance(exc, BenchmarkProviderError):
                raise
            raise BenchmarkProviderError(f"Gnani TTS failed: {exc}") from exc
        finally:
            await adapter.close()
        finished = time.perf_counter()
        if first_audio is None or not audio:
            raise BenchmarkProviderError("Gnani TTS returned no audio.")
        return TTSResult(
            audio_bytes=bytes(audio),
            t_request_sent=request_sent,
            t_first_audio_byte=first_audio,
            t_done=finished,
        )

    async def close(self) -> None:
        return None


__all__ = ["GnaniTTS"]
