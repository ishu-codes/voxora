"""Environment-driven configuration for the Voxora voice service.

Speech recognition and synthesis are fixed to Sarvam's streaming models. The
language model is still provider-agnostic because any OpenAI-compatible
endpoint (DeepSeek, Groq, Ollama, vLLM) speaks the same protocol.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
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

    # Sarvam connection
    sarvam_api_key: str = ""
    sarvam_ws_url: str = "wss://api.sarvam.ai"

    # Speech to text (Sarvam Saaras, realtime WebSocket)
    stt_model: str = "saaras:v3-realtime"
    stt_language: str = "en-IN"
    stt_stream_type: str = "fast"
    stt_mode: str = "transcribe"
    stt_timeout_s: float = 30.0

    # LLM (any OpenAI-compatible endpoint)
    llm_provider: str = "auto"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_temperature: float = 0.7
    llm_max_tokens: int = 320
    llm_timeout_s: float = 60.0
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    # Text to speech (Sarvam Bulbul, streaming WebSocket)
    tts_model: str = "bulbul:v3"
    tts_voice: str = "shubh"
    tts_language: str = "en-IN"
    tts_sample_rate: int = 22_050
    tts_speed: float = 1.0
    tts_temperature: float = 0.6
    tts_timeout_s: float = 60.0

    # Voice activity detection / turn taking
    vad_threshold: float = 0.014
    vad_start_frames: int = 3
    vad_end_silence_ms: int = 650
    vad_pre_roll_ms: int = 300
    vad_max_utterance_ms: int = 30_000

    # Limits
    max_history_messages: int = 24
    max_output_queue: int = 256
    # Platform keys are shared, so anonymous sessions get a bounded trial.
    # Sessions that bring a Sarvam key plus an OpenAI-compatible endpoint do
    # not use this limit.
    platform_max_turns: int = 20

    # Diagnostics
    log_level: str = "INFO"
    store_recent_turns: int = 500

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
            sarvam_api_key=_env("SARVAM_API_KEY"),
            sarvam_ws_url=_env("SARVAM_WS_URL", "wss://api.sarvam.ai").rstrip("/"),
            stt_model=_env("STT_MODEL", "saaras:v3-realtime"),
            stt_language=_env("STT_LANGUAGE", "en-IN"),
            stt_stream_type=_env("STT_STREAM_TYPE", "fast").lower(),
            stt_mode=_env("STT_MODE", "transcribe").lower(),
            stt_timeout_s=_env_float("STT_TIMEOUT_S", 30.0),
            llm_provider=_env("LLM_PROVIDER", "auto").lower(),
            llm_model=_env("LLM_MODEL", "gpt-4o-mini"),
            llm_base_url=_env("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_api_key=_env("LLM_API_KEY"),
            llm_temperature=_env_float("LLM_TEMPERATURE", 0.7),
            llm_max_tokens=_env_int("LLM_MAX_TOKENS", 320),
            llm_timeout_s=_env_float("LLM_TIMEOUT_S", 60.0),
            system_prompt=_env("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
            tts_model=_env("TTS_MODEL", "bulbul:v3"),
            tts_voice=_env("TTS_VOICE", "shubh"),
            tts_language=_env("TTS_LANGUAGE", "en-IN"),
            tts_sample_rate=_env_int("TTS_SAMPLE_RATE", 22_050),
            tts_speed=_env_float("TTS_SPEED", 1.0),
            tts_temperature=_env_float("TTS_TEMPERATURE", 0.6),
            tts_timeout_s=_env_float("TTS_TIMEOUT_S", 60.0),
            vad_threshold=_env_float("VAD_THRESHOLD", 0.014),
            vad_start_frames=_env_int("VAD_START_FRAMES", 3),
            vad_end_silence_ms=_env_int("VAD_END_SILENCE_MS", 650),
            vad_pre_roll_ms=_env_int("VAD_PRE_ROLL_MS", 300),
            vad_max_utterance_ms=_env_int("VAD_MAX_UTTERANCE_MS", 30_000),
            max_history_messages=_env_int("MAX_HISTORY_MESSAGES", 24),
            max_output_queue=_env_int("MAX_OUTPUT_QUEUE", 256),
            platform_max_turns=_env_int("PLATFORM_MAX_TURNS", 20),
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
