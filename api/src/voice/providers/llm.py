"""Streaming language-model adapters.

Both hosted OpenAI-compatible APIs and local servers (Ollama, vLLM, llama.cpp)
speak the same chat-completions protocol, so one adapter covers them.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import httpx

from ..core.config import Settings
from .base import ProviderError, provider_http_error

logger = logging.getLogger(__name__)


class EchoLLM:
    """Zero-configuration demo responder.

    It is intentionally honest about being a stub so a fresh checkout can
    exercise audio capture, VAD, barge-in and playback before any model key is
    configured.
    """

    name = "echo (demo)"
    streaming = True

    async def _stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        user_text = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                user_text = message.get("content", "")
                break
        reply = (
            "I am running in local demo mode, so I cannot answer that fully yet. "
            f"You said: {user_text.strip()} "
            "To get real spoken answers, set the LLM provider and an API key on the server."
        )
        for token in reply.split(" "):
            yield token + " "
            await asyncio.sleep(0.012)

    def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        return self._stream(messages)

    async def close(self) -> None:
        return None


class OpenAICompatibleLLM:
    name = "openai-compatible"
    streaming = True

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.llm_base_url,
            timeout=httpx.Timeout(settings.llm_timeout_s, connect=10.0),
            headers={"Authorization": f"Bearer {self._settings.llm_api_key}"},
        )

    async def _stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        payload = {
            "model": self._settings.llm_model,
            "messages": messages,
            "stream": True,
            "temperature": self._settings.llm_temperature,
            "max_tokens": self._settings.llm_max_tokens,
        }
        try:
            async with self._client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")
                    raise provider_http_error(
                        "llm", "Language model", response.status_code, body
                    )
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                    else:
                        data = line.strip()
                    if data == "[DONE]":
                        return
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    token = delta.get("content")
                    if token:
                        yield token
        except httpx.HTTPError as exc:
            raise ProviderError("llm", f"Language model request failed: {exc}") from exc

    def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        return self._stream(messages)

    async def close(self) -> None:
        await self._client.aclose()


def build_llm(settings: Settings) -> tuple[EchoLLM | OpenAICompatibleLLM, str]:
    choice = settings.llm_provider
    if choice == "echo":
        return EchoLLM(), "configured"
    if choice in {"openai", "openai-compatible", "groq", "ollama", "vllm", "custom"}:
        return OpenAICompatibleLLM(settings), "configured"
    if settings.llm_api_key:
        return OpenAICompatibleLLM(settings), "auto: API key present"
    return EchoLLM(), "auto: no LLM key, using demo responder"


__all__ = ["EchoLLM", "OpenAICompatibleLLM", "build_llm"]
