"""Environment-driven configuration for the Voxora voice service.

Every provider choice is externalised here so the rest of the application only
talks to the interfaces in :mod:`src.voice.providers.base`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SAMPLE_RATE = 16_000
FRAME_MS = 20
BYTES_PER_SAMPLE = 2
FRAME_BYTES = SAMPLE_RATE * FRAME_MS // 1000 * BYTES_PER_SAMPLE  # 640 bytes


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name, "true" if default else "false").lower()
    return value in {"1", "true", "yes", "on"}


DEFAULT_SYSTEM_PROMPT = (
    "You are Voxora, a friendly real-time voice assistant. Your replies are "
    "spoken aloud, so answer in plain conversational language. Never use "
    "markdown, bullet lists, headings, emoji, or code fences. Keep most "
    "answers to two or three short sentences unless the user asks for depth. "
    "If you are unsure, say so briefly instead of inventing details."
)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Voxora"
    version: str = "0.1.0"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)

    # Speech to text
    stt_provider: str = "auto"
    stt_model: str = "whisper-1"
    stt_language: str = ""
    stt_base_url: str = "https://api.openai.com/v1"
    stt_api_key: str = ""
    whisper_model: str = "base"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"

    # LLM
    llm_provider: str = "auto"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_temperature: float = 0.7
    llm_max_tokens: int = 320
    llm_timeout_s: float = 60.0
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    # TTS
    tts_provider: str = "auto"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"
    tts_base_url: str = "https://api.openai.com/v1"
    tts_api_key: str = ""
    tts_sample_rate: int = 24_000
    tts_timeout_s: float = 60.0
    tts_speed: float = 1.0

    # Voice activity detection / turn taking
    vad_threshold: float = 0.014
    vad_start_frames: int = 3
    vad_end_silence_ms: int = 650
    vad_pre_roll_ms: int = 300
    vad_max_utterance_ms: int = 30_000
    browser_transcript_timeout_s: float = 4.0

    # Limits
    max_history_messages: int = 24
    max_output_queue: int = 256

    # Diagnostics
    log_level: str = "INFO"
    store_recent_turns: int = 500

    @property
    def openai_key(self) -> str:
        """A single key can serve all three hosted adapters."""
        return self.llm_api_key or self.stt_api_key or self.tts_api_key or _env("OPENAI_API_KEY")

    def key_for(self, stage: str) -> str:
        explicit = {
            "stt": self.stt_api_key,
            "llm": self.llm_api_key,
            "tts": self.tts_api_key,
        }[stage]
        if explicit:
            return explicit
        # Provider-specific keys are convenient when mixing vendors.
        provider = {
            "stt": self.stt_provider,
            "llm": self.llm_provider,
            "tts": self.tts_provider,
        }[stage]
        if provider in {"groq", "openai", "openai-compatible", "auto"}:
            env_key = _env("OPENAI_API_KEY") or _env("GROQ_API_KEY")
            if env_key:
                return env_key
        if provider == "ollama":
            return _env("OLLAMA_API_KEY", "ollama")
        return ""

    @classmethod
    def from_env(cls) -> "Settings":
        origins = tuple(
            origin.strip()
            for origin in _env("CORS_ORIGINS", "http://localhost:3000").split(",")
            if origin.strip()
        )
        return cls(
            app_name=_env("APP_NAME", "Voxora"),
            cors_origins=origins or ("http://localhost:3000",),
            stt_provider=_env("STT_PROVIDER", "auto").lower(),
            stt_model=_env("STT_MODEL", "whisper-1"),
            stt_language=_env("STT_LANGUAGE", ""),
            stt_base_url=_env("STT_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            stt_api_key=_env("STT_API_KEY"),
            whisper_model=_env("WHISPER_MODEL", "base"),
            whisper_device=_env("WHISPER_DEVICE", "auto"),
            whisper_compute_type=_env("WHISPER_COMPUTE_TYPE", "int8"),
            llm_provider=_env("LLM_PROVIDER", "auto").lower(),
            llm_model=_env("LLM_MODEL", "gpt-4o-mini"),
            llm_base_url=_env("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_api_key=_env("LLM_API_KEY"),
            llm_temperature=_env_float("LLM_TEMPERATURE", 0.7),
            llm_max_tokens=_env_int("LLM_MAX_TOKENS", 320),
            llm_timeout_s=_env_float("LLM_TIMEOUT_S", 60.0),
            system_prompt=_env("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
            tts_provider=_env("TTS_PROVIDER", "auto").lower(),
            tts_model=_env("TTS_MODEL", "gpt-4o-mini-tts"),
            tts_voice=_env("TTS_VOICE", "alloy"),
            tts_base_url=_env("TTS_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            tts_api_key=_env("TTS_API_KEY"),
            tts_sample_rate=_env_int("TTS_SAMPLE_RATE", 24_000),
            tts_timeout_s=_env_float("TTS_TIMEOUT_S", 60.0),
            tts_speed=_env_float("TTS_SPEED", 1.0),
            vad_threshold=_env_float("VAD_THRESHOLD", 0.014),
            vad_start_frames=_env_int("VAD_START_FRAMES", 3),
            vad_end_silence_ms=_env_int("VAD_END_SILENCE_MS", 650),
            vad_pre_roll_ms=_env_int("VAD_PRE_ROLL_MS", 300),
            vad_max_utterance_ms=_env_int("VAD_MAX_UTTERANCE_MS", 30_000),
            browser_transcript_timeout_s=_env_float("BROWSER_TRANSCRIPT_TIMEOUT_S", 4.0),
            max_history_messages=_env_int("MAX_HISTORY_MESSAGES", 24),
            max_output_queue=_env_int("MAX_OUTPUT_QUEUE", 256),
            log_level=_env("LOG_LEVEL", "INFO").upper(),
            store_recent_turns=_env_int("STORE_RECENT_TURNS", 500),
        )


settings = Settings.from_env()

__all__ = [
    "Settings",
    "settings",
    "SAMPLE_RATE",
    "FRAME_MS",
    "FRAME_BYTES",
    "BYTES_PER_SAMPLE",
    "DEFAULT_SYSTEM_PROMPT",
]
