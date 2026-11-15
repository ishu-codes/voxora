"""Server-managed provider construction and ownership."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..core.config import Settings
from ..providers import SarvamSTT, SarvamTTS, WhisperEngine, WhisperSTT, build_llm
from ..providers.base import LLMProvider, ProviderError, STTProvider

logger = logging.getLogger(__name__)


@dataclass
class ProviderBundle:
    """Provider state for one settings snapshot."""

    settings: Settings
    llm: LLMProvider
    whisper_engine: WhisperEngine | None = None
    reasons: dict[str, str] = field(default_factory=dict)

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
        if config.stt_provider == "whisper":
            whisper_engine = WhisperEngine.load()
        elif config.stt_provider != "sarvam":
            raise ProviderError(
                "stt",
                f"Unsupported STT provider {config.stt_provider!r}.",
            )
        return cls.build(config, whisper_engine)

    def new_stt(self, session_id: str = "") -> STTProvider:
        if self.settings.stt_provider == "whisper":
            if self.whisper_engine is None:
                raise ProviderError("stt", "Local Whisper is not initialized.")
            return WhisperSTT(self.whisper_engine, self.settings, session_id)
        return SarvamSTT(self.settings, session_id)

    def new_tts(self, session_id: str = "") -> SarvamTTS:
        return SarvamTTS(self.settings, session_id)

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
