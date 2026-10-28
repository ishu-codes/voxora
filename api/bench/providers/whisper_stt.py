"""OpenAI Whisper speech-to-text adapter."""

from __future__ import annotations

import asyncio
import io
import time
import wave
from pathlib import Path

import httpx

from bench.core.config import BenchmarkConfig
from bench.providers.base import BenchmarkProviderError, STTResult
from bench.utils.audio import convert_to_pcm16_mono


class WhisperSTT:
    name = "openai-whisper"
    mode = "transcribe"

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self.model = str(config.whisper["model"])
        self._client = httpx.AsyncClient(
            base_url=config.whisper_base_url,
            timeout=httpx.Timeout(float(config.whisper["timeout_s"]), connect=10),
            headers={"Authorization": f"Bearer {config.whisper_api_key}"},
        )

    def metadata(self, language_hint: str | None) -> dict[str, object]:
        return {
            "device": "cloud",
            "compute_type": None,
            "model_size": self.model,
            "beam_size": None,
            "language_hint": {"en": "en", "hi": "hi", "hinglish": "hi"}.get(
                language_hint or ""
            ),
            "declared_sample_rate_hz": self.config.sample_rate,
        }

    async def transcribe_file(
        self,
        wav_path: str,
        language_hint: str | None,
    ) -> STTResult:
        if not self.config.whisper_api_key:
            raise BenchmarkProviderError(
                "Whisper API key is not configured. Set WHISPER_API_KEY."
            )
        audio = convert_to_pcm16_mono(wav_path, self.config.sample_rate)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav:
            wav.setnchannels(audio.channels)
            wav.setsampwidth(audio.sample_width_bytes)
            wav.setframerate(audio.sample_rate_hz)
            wav.writeframes(audio.pcm)
        language = {"en": "en", "hi": "hi", "hinglish": "hi"}.get(
            language_hint or ""
        )
        request_sent = time.perf_counter()
        for attempt in range(self.config.retry_attempts):
            try:
                files = {
                    "file": (
                        Path(wav_path).name,
                        wav_buffer.getvalue(),
                        "audio/wav",
                    )
                }
                data = {"model": self.model, "response_format": "json"}
                if language:
                    data["language"] = language
                response = await self._client.post(
                    "/audio/transcriptions",
                    files=files,
                    data=data,
                )
                if response.status_code in {401, 403}:
                    raise BenchmarkProviderError(
                        "Whisper authentication failed. Check WHISPER_API_KEY."
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    raise BenchmarkProviderError(
                        f"Whisper transient HTTP {response.status_code}: "
                        f"{response.text[:180]}"
                    )
                if response.status_code >= 400:
                    raise BenchmarkProviderError(
                        f"Whisper HTTP {response.status_code}: "
                        f"{response.text[:180]}"
                    )
                payload = response.json()
                finished = time.perf_counter()
                return STTResult(
                    text=str(payload.get("text", "")).strip(),
                    t_request_sent=request_sent,
                    t_first_partial=None,
                    t_final=finished,
                    provider=self.name,
                    model=self.model,
                    mode=self.mode,
                )
            except BenchmarkProviderError as exc:
                if "authentication" in str(exc).lower():
                    raise
                if attempt + 1 >= self.config.retry_attempts:
                    raise
            except httpx.HTTPError as exc:
                if attempt + 1 >= self.config.retry_attempts:
                    raise BenchmarkProviderError(
                        f"Whisper request failed: {exc}"
                    ) from exc
            delay = min(
                self.config.retry_base_delay * (2**attempt),
                self.config.retry_max_delay,
            )
            await asyncio.sleep(delay)
        raise BenchmarkProviderError("Whisper request failed after retries.")

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["WhisperSTT"]
