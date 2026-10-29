"""Streaming OpenAI-compatible language-model client."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

import httpx

from bench.core.config import BenchmarkConfig, ProviderConfig
from bench.providers.base import BenchmarkProviderError


class LLMClient:
    def __init__(
        self,
        config: BenchmarkConfig,
        provider: ProviderConfig | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self.config = config
        provider = provider or config.llm
        self.model = model or (
            config.llm_model if provider is config.llm else provider.model
        )
        self.temperature = (
            provider.temperature if temperature is None else temperature
        )
        self._api_key = api_key if api_key is not None else config.llm_api_key
        resolved_base = base_url or (
            config.llm_base_url if provider is config.llm else provider.base_url
        )
        self._client = httpx.AsyncClient(
            base_url=resolved_base.rstrip("/"),
            timeout=httpx.Timeout(provider.timeout_s, connect=10.0),
        )
        self._max_tokens = provider.max_tokens
        self._thinking = provider.thinking

    async def stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[tuple[str, float]]:
        if not self._api_key:
            raise BenchmarkProviderError(
                "LLM API key is not configured. Set LLM_API_KEY."
            )
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature,
            "max_tokens": self._max_tokens,
        }
        if self._thinking:
            payload["thinking"] = {"type": self._thinking}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        for attempt in range(self.config.retry_attempts):
            yielded = False
            try:
                async with self._client.stream(
                    "POST",
                    "/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status_code in {401, 403}:
                        raise BenchmarkProviderError(
                            "Language model authentication failed. "
                            "Check LLM_API_KEY."
                        )
                    if response.status_code == 429 or response.status_code >= 500:
                        body = (await response.aread()).decode("utf-8", "replace")
                        raise BenchmarkProviderError(
                            f"Language model transient HTTP {response.status_code}: "
                            f"{body[:180]}"
                        )
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", "replace")
                        raise BenchmarkProviderError(
                            f"Language model HTTP {response.status_code}: "
                            f"{body[:180]}"
                        )
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = line[5:].strip() if line.startswith("data:") else line
                        if data == "[DONE]":
                            return
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = event.get("choices") or []
                        if not choices:
                            continue
                        token = (choices[0].get("delta") or {}).get("content")
                        if token:
                            yielded = True
                            yield token, time.perf_counter()
                    return
            except BenchmarkProviderError:
                if yielded or attempt + 1 >= self.config.retry_attempts:
                    raise
            except httpx.HTTPError as exc:
                if yielded or attempt + 1 >= self.config.retry_attempts:
                    raise BenchmarkProviderError(
                        f"Language model request failed: {exc}"
                    ) from exc
            delay = min(
                self.config.retry_base_delay * (2**attempt),
                self.config.retry_max_delay,
            )
            await asyncio.sleep(delay)
        raise BenchmarkProviderError("Language model request failed after retries.")

    async def complete(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        for attempt in range(4):
            parts = [token async for token, _ in self.stream(messages)]
            text = "".join(parts).strip()
            if text:
                return text
            if attempt < 3:
                await asyncio.sleep(2**attempt)
        raise BenchmarkProviderError("Language model returned an empty response.")

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["LLMClient"]
