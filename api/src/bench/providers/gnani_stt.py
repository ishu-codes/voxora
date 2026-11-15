"""Gnani Prisma v2.5 REST adapter for the STT benchmark."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx

from bench.core.config import BenchmarkConfig
from bench.providers.base import BenchmarkProviderError, STTResult

_LANGUAGE = {
    "en": "en-IN",
    "hi": "hi-IN",
    "hinglish": "hi-IN",
}


class GnaniSTT:
    name = "gnani-prisma"

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self.model = str(config.gnani["stt_model"])
        self.mode = str(config.gnani.get("stt_format", "verbatim"))
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(float(config.gnani["timeout_s"]), connect=10.0),
            headers={
                "X-API-Key-ID": config.gnani_api_key,
                "Accept": "application/json",
            },
        )

    def metadata(self, language_hint: str | None) -> dict[str, object]:
        return {
            "device": "cloud",
            "compute_type": None,
            "model_size": self.model,
            "beam_size": None,
            "language_hint": _LANGUAGE.get(language_hint or ""),
            "declared_sample_rate_hz": None,
        }

    async def transcribe_file(
        self,
        wav_path: str,
        language_hint: str | None,
    ) -> STTResult:
        if not self.config.gnani_api_key:
            raise BenchmarkProviderError(
                "Gnani API key is not configured. Set GNANI_API_KEY."
            )
        language = _LANGUAGE.get(language_hint or "")
        if not language:
            raise BenchmarkProviderError(
                f"Unsupported benchmark language hint {language_hint!r}."
            )
        path = Path(wav_path)
        last_error: Exception | None = None
        for attempt in range(self.config.retry_attempts):
            request_sent = time.perf_counter()
            try:
                with path.open("rb") as audio:
                    response = await self._client.post(
                        str(self.config.gnani["stt_url"]),
                        files={"audio_file": (path.name, audio, "audio/wav")},
                        data={
                            "model": self.model,
                            "language_code": language,
                            "format": self.mode,
                        },
                    )
                finished = time.perf_counter()
                if response.status_code in {401, 402, 403}:
                    detail = _error_message(response)
                    raise BenchmarkProviderError(
                        f"Gnani authentication or credit failure "
                        f"({response.status_code}): {detail}"
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    raise BenchmarkProviderError(
                        f"Gnani transient HTTP {response.status_code}: "
                        f"{_error_message(response)}"
                    )
                if response.status_code >= 400:
                    raise BenchmarkProviderError(
                        f"Gnani HTTP {response.status_code}: "
                        f"{_error_message(response)}"
                    )
                payload = response.json()
                if payload.get("success") is not True:
                    raise BenchmarkProviderError(
                        f"Gnani returned unsuccessful response: "
                        f"{_error_message(response)}"
                    )
                return STTResult(
                    text=str(payload.get("transcript") or "").strip(),
                    t_request_sent=request_sent,
                    t_first_partial=None,
                    t_final=finished,
                    provider=self.name,
                    model=str(payload.get("model") or self.model),
                    mode=self.mode,
                )
            except BenchmarkProviderError as exc:
                last_error = exc
                message = str(exc).lower()
                if (
                    "authentication" in message
                    or "credit" in message
                    or attempt + 1 >= self.config.retry_attempts
                ):
                    raise
            except (httpx.HTTPError, OSError, ValueError) as exc:
                last_error = exc
                if attempt + 1 >= self.config.retry_attempts:
                    raise BenchmarkProviderError(
                        f"Gnani request failed: {exc}"
                    ) from exc
            delay = min(
                self.config.retry_base_delay * (2**attempt),
                self.config.retry_max_delay,
            )
            await asyncio.sleep(delay)
        raise BenchmarkProviderError(
            f"Gnani request failed after retries: {last_error}"
        ) from last_error

    async def close(self) -> None:
        await self._client.aclose()


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return " ".join(response.text.split())[:200]
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("type") or "")[:200]
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("error_code") or "")[:200]
    return str(payload.get("message") or "")[:200]


__all__ = ["GnaniSTT"]
