"""Environment-driven configuration for the Voxora voice service.

Speech recognition and synthesis can use Sarvam, Gnani or the local Whisper
model. The provider chosen in the browser overrides the server default for one
session, but credentials always remain server-side.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

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


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(
        item.strip() for item in _env(name, default).split(",") if item.strip()
    )


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
    allowed_unlimited: tuple[str, ...] = ()

    # Sarvam connection
    sarvam_api_key: str = ""
    sarvam_ws_url: str = "wss://api.sarvam.ai"

    # Speech to text (Gnani Prisma by default)
    stt_provider: str = "gnani"
    stt_model: str = "saaras:v3-realtime"
    stt_language: str = "en-IN"
    stt_stream_type: str = "fast"
    stt_mode: str = "transcribe"
    stt_timeout_s: float = 30.0
    whisper_language: str = "auto"

    # Gnani Prisma v2.5 streaming speech to text
    gnani_api_key: str = ""
    gnani_stt_url: str = "wss://api.vachana.ai/stt/v3/stream"
    gnani_stt_model: str = "prisma-v2.5"
    gnani_stt_language: str = "hi-IN"
    gnani_stt_format: str = "verbatim"

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
    tts_provider: str = "gnani"
    tts_model: str = "bulbul:v3"
    tts_voice: str = "shubh"
    tts_language: str = "en-IN"
    tts_sample_rate: int = 22_050
    tts_speed: float = 1.0
    tts_temperature: float = 0.6
    tts_timeout_s: float = 60.0

    # Gnani Timbre v2.5 realtime speech synthesis
    gnani_tts_url: str = "wss://api.vachana.ai/api/v1/tts"
    gnani_tts_model: str = "timbre-v2.5"
    gnani_tts_voice: str = "Kaveri"
    gnani_tts_language: str = "hi-en"

    # Provider retries are deliberately bounded. Requests run one at a time.
    provider_retry_attempts: int = 3
    provider_retry_base_ms: int = 750

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
    platform_max_turns: int = 10

    # Strict abuse controls. These are evaluated across WebSocket sessions,
    # unlike platform_max_turns which applies to one connection.
    rate_limit_enabled: bool = True
    require_browser_client: bool = True
    rate_limit_secret: str = ""
    trust_proxy_headers: bool = False
    rate_limit_ip_attempts_10m: int = 30
    rate_limit_ip_attempts_day: int = 200
    rate_limit_identity_attempts_10m: int = 5
    rate_limit_identity_sessions_hour: int = 10
    rate_limit_identity_sessions_day: int = 20
    rate_limit_platform_turns_hour: int = 10
    # A rolling hourly quota naturally caps a continuously active caller at 240
    # turns over 24 hours. Keep the wider window aligned with that bound.
    rate_limit_platform_turns_day: int = 240
    rate_limit_stt_chars_hour: int = 30_000
    rate_limit_stt_chars_day: int = 120_000
    rate_limit_llm_chars_hour: int = 30_000
    rate_limit_llm_chars_day: int = 120_000
    rate_limit_llm_tokens_hour: int = 8_000
    rate_limit_llm_tokens_day: int = 32_000
    rate_limit_tts_chars_hour: int = 30_000
    rate_limit_tts_chars_day: int = 120_000
    rate_limit_max_concurrent_identity: int = 1
    rate_limit_max_session_seconds: int = 900

    # Diagnostics
    log_level: str = "INFO"
    store_recent_turns: int = 500

    def ip_is_unlimited(self, value: str) -> bool:
        """Return true when a caller IP is explicitly exempted by the operator."""
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            return False
        for entry in self.allowed_unlimited:
            try:
                if address in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                continue
        return False

    @classmethod
    def from_env(cls) -> "Settings":
        origins = _env_csv("CORS_ORIGINS", "http://localhost:3000")
        return cls(
            app_name=_env("APP_NAME", "Voxora"),
            cors_origins=origins or ("http://localhost:3000",),
            allowed_unlimited=_env_csv("ALLOWED_UNLIMITED"),
            sarvam_api_key=_env("SARVAM_API_KEY"),
            sarvam_ws_url=_env("SARVAM_WS_URL", "wss://api.sarvam.ai").rstrip("/"),
            stt_provider=_env("STT_PROVIDER", "gnani").lower(),
            stt_model=_env("STT_MODEL", "saaras:v3-realtime"),
            stt_language=_env("STT_LANGUAGE", "en-IN"),
            stt_stream_type=_env("STT_STREAM_TYPE", "fast").lower(),
            stt_mode=_env("STT_MODE", "transcribe").lower(),
            stt_timeout_s=_env_float("STT_TIMEOUT_S", 30.0),
            whisper_language=_env("WHISPER_LANGUAGE", "auto"),
            gnani_api_key=_env("GNANI_API_KEY"),
            gnani_stt_url=_env(
                "GNANI_STT_URL",
                "wss://api.vachana.ai/stt/v3/stream",
            ),
            gnani_stt_model=_env("GNANI_STT_MODEL", "prisma-v2.5"),
            gnani_stt_language=_env("GNANI_STT_LANGUAGE", "hi-IN"),
            gnani_stt_format=_env("GNANI_STT_FORMAT", "verbatim").lower(),
            llm_provider=_env("LLM_PROVIDER", "auto").lower(),
            llm_model=_env("LLM_MODEL", "gpt-4o-mini"),
            llm_base_url=_env("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_api_key=_env("LLM_API_KEY"),
            llm_temperature=_env_float("LLM_TEMPERATURE", 0.7),
            llm_max_tokens=_env_int("LLM_MAX_TOKENS", 320),
            llm_timeout_s=_env_float("LLM_TIMEOUT_S", 60.0),
            system_prompt=_env("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
            tts_provider=_env("TTS_PROVIDER", "gnani").lower(),
            tts_model=_env("TTS_MODEL", "bulbul:v3"),
            tts_voice=_env("TTS_VOICE", "shubh"),
            tts_language=_env("TTS_LANGUAGE", "en-IN"),
            tts_sample_rate=_env_int("TTS_SAMPLE_RATE", 22_050),
            tts_speed=_env_float("TTS_SPEED", 1.0),
            tts_temperature=_env_float("TTS_TEMPERATURE", 0.6),
            tts_timeout_s=_env_float("TTS_TIMEOUT_S", 60.0),
            gnani_tts_url=_env(
                "GNANI_TTS_URL",
                "wss://api.vachana.ai/api/v1/tts",
            ),
            gnani_tts_model=_env("GNANI_TTS_MODEL", "timbre-v2.5"),
            gnani_tts_voice=_env("GNANI_TTS_VOICE", "Kaveri"),
            gnani_tts_language=_env("GNANI_TTS_LANGUAGE", "hi-en"),
            provider_retry_attempts=_env_int("PROVIDER_RETRY_ATTEMPTS", 3),
            provider_retry_base_ms=_env_int("PROVIDER_RETRY_BASE_MS", 750),
            vad_threshold=_env_float("VAD_THRESHOLD", 0.014),
            vad_start_frames=_env_int("VAD_START_FRAMES", 3),
            vad_end_silence_ms=_env_int("VAD_END_SILENCE_MS", 650),
            vad_pre_roll_ms=_env_int("VAD_PRE_ROLL_MS", 300),
            vad_max_utterance_ms=_env_int("VAD_MAX_UTTERANCE_MS", 30_000),
            max_history_messages=_env_int("MAX_HISTORY_MESSAGES", 24),
            max_output_queue=_env_int("MAX_OUTPUT_QUEUE", 256),
            platform_max_turns=_env_int("PLATFORM_MAX_TURNS", 10),
            rate_limit_enabled=_env_bool("RATE_LIMIT_ENABLED", True),
            require_browser_client=_env_bool("REQUIRE_BROWSER_CLIENT", True),
            rate_limit_secret=_env("RATE_LIMIT_SECRET"),
            trust_proxy_headers=_env_bool("TRUST_PROXY_HEADERS", False),
            rate_limit_ip_attempts_10m=_env_int("RATE_LIMIT_IP_ATTEMPTS_10M", 30),
            rate_limit_ip_attempts_day=_env_int("RATE_LIMIT_IP_ATTEMPTS_DAY", 200),
            rate_limit_identity_attempts_10m=_env_int(
                "RATE_LIMIT_IDENTITY_ATTEMPTS_10M", 5
            ),
            rate_limit_identity_sessions_hour=_env_int(
                "RATE_LIMIT_IDENTITY_SESSIONS_HOUR", 10
            ),
            rate_limit_identity_sessions_day=_env_int(
                "RATE_LIMIT_IDENTITY_SESSIONS_DAY", 20
            ),
            rate_limit_platform_turns_hour=_env_int(
                "RATE_LIMIT_PLATFORM_TURNS_HOUR", 10
            ),
            rate_limit_platform_turns_day=_env_int(
                "RATE_LIMIT_PLATFORM_TURNS_DAY", 240
            ),
            rate_limit_stt_chars_hour=_env_int(
                "RATE_LIMIT_STT_CHARS_HOUR", 30_000
            ),
            rate_limit_stt_chars_day=_env_int(
                "RATE_LIMIT_STT_CHARS_DAY", 120_000
            ),
            rate_limit_llm_chars_hour=_env_int(
                "RATE_LIMIT_LLM_CHARS_HOUR", 30_000
            ),
            rate_limit_llm_chars_day=_env_int(
                "RATE_LIMIT_LLM_CHARS_DAY", 120_000
            ),
            rate_limit_llm_tokens_hour=_env_int(
                "RATE_LIMIT_LLM_TOKENS_HOUR", 8_000
            ),
            rate_limit_llm_tokens_day=_env_int(
                "RATE_LIMIT_LLM_TOKENS_DAY", 32_000
            ),
            rate_limit_tts_chars_hour=_env_int(
                "RATE_LIMIT_TTS_CHARS_HOUR", 30_000
            ),
            rate_limit_tts_chars_day=_env_int(
                "RATE_LIMIT_TTS_CHARS_DAY", 120_000
            ),
            rate_limit_max_concurrent_identity=_env_int(
                "RATE_LIMIT_MAX_CONCURRENT_IDENTITY", 1
            ),
            rate_limit_max_session_seconds=_env_int(
                "RATE_LIMIT_MAX_SESSION_SECONDS", 900
            ),
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
