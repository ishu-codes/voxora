"""Server-managed provider construction and ownership."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from ..core.config import Settings
from ..providers import (
    GnaniSTT,
    GnaniTTS,
    SarvamSTT,
    SarvamTTS,
    WhisperEngine,
    WhisperSTT,
    build_llm,
)
from ..providers.base import LLMProvider, ProviderError, STTProvider

logger = logging.getLogger(__name__)


@dataclass
class ProviderBundle:
    """Provider state for one settings snapshot."""

    settings: Settings
    llm: LLMProvider
    whisper_engine: WhisperEngine | None = None
    reasons: dict[str, str] = field(default_factory=dict)
    whisper_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @classmethod
    def build(
        cls,
        config: Settings,
        whisper_engine: WhisperEngine | None = None,
    ) -> ProviderBundle:
        llm, llm_reason = build_llm(config)
        return cls(
            settings=config,
            llm=llm,
            whisper_engine=whisper_engine,
            reasons={"llm": llm_reason},
        )

    @classmethod
    async def initialize(cls, config: Settings) -> ProviderBundle:
        whisper_engine = None
        if config.stt_provider in {"whisper", "faster-whisper"}:
            whisper_engine = WhisperEngine.load()
        elif config.stt_provider not in {"sarvam", "gnani"}:
            raise ProviderError(
                "stt",
                f"Unsupported STT provider {config.stt_provider!r}.",
            )
        if config.tts_provider not in {"sarvam", "gnani"}:
            raise ProviderError(
                "tts",
                f"Unsupported TTS provider {config.tts_provider!r}.",
            )
        return cls.build(config, whisper_engine)

    async def new_stt(
        self,
        session_id: str = "",
        provider: str | None = None,
        settings: Settings | None = None,
    ) -> STTProvider:
        selected = (provider or self.settings.stt_provider).lower()
        active_settings = settings or self.settings
        if selected in {"whisper", "faster-whisper"}:
            if self.whisper_engine is None:
                async with self.whisper_lock:
                    if self.whisper_engine is None:
                        loop = asyncio.get_running_loop()
                        self.whisper_engine = await loop.run_in_executor(
                            None,
                            WhisperEngine.load,
                        )
            return WhisperSTT(self.whisper_engine, active_settings, session_id)
        if selected == "sarvam":
            return SarvamSTT(active_settings, session_id)
        if selected == "gnani":
            return GnaniSTT(active_settings, session_id)
        raise ProviderError("stt", f"Unsupported STT provider {selected!r}.")

    def new_tts(
        self,
        session_id: str = "",
        provider: str | None = None,
        settings: Settings | None = None,
    ) -> SarvamTTS | GnaniTTS:
        selected = (provider or self.settings.tts_provider).lower()
        active_settings = settings or self.settings
        if selected == "sarvam":
            return SarvamTTS(active_settings, session_id)
        if selected == "gnani":
            return GnaniTTS(active_settings, session_id)
        raise ProviderError("tts", f"Unsupported TTS provider {selected!r}.")

    async def close(self) -> None:
        try:
            await self.llm.close()
        except Exception:  # pragma: no cover - best effort cleanup
            logger.debug("Provider close failed", exc_info=True)
        if self.whisper_engine is not None:
            self.whisper_engine.close()


def get_or_create_bundle(state: Any, config: Settings) -> ProviderBundle:
    """Return the app-level provider bundle, creating it once if needed."""
    bundle = getattr(state, "voice_providers", None)
    if bundle is None:
        bundle = ProviderBundle.build(config)
        state.voice_providers = bundle
    return bundle


async def shutdown_providers(app: Any) -> None:
    """Close providers owned by the application."""
    bundle = getattr(app.state, "voice_providers", None)
    if bundle is not None:
        await bundle.close()
        app.state.voice_providers = None


__all__ = ["ProviderBundle", "get_or_create_bundle", "shutdown_providers"]
