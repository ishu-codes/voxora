"""Typed access to the benchmark YAML and environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT.parent
CONFIG_PATH = API_ROOT / "config.yaml"

load_dotenv(API_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    base_url: str
    temperature: float
    max_tokens: int
    timeout_s: float
    thinking: str | None = None


@dataclass(frozen=True)
class BenchmarkConfig:
    raw: dict[str, Any]
    root: Path = ROOT

    @property
    def stt(self) -> dict[str, Any]:
        return self.raw["providers"]["stt"]

    @property
    def whisper(self) -> dict[str, Any]:
        return self.raw["providers"]["whisper"]

    @property
    def faster_whisper(self) -> dict[str, Any]:
        return self.raw["providers"]["faster_whisper"]

    @property
    def tts(self) -> dict[str, Any]:
        return self.raw["providers"]["tts"]

    @property
    def gnani(self) -> dict[str, Any]:
        return self.raw["providers"]["gnani"]

    @property
    def llm(self) -> ProviderConfig:
        return self._provider("llm")

    @property
    def classification(self) -> dict[str, Any]:
        return self.raw["providers"]["classification"]

    @property
    def sample_rate(self) -> int:
        return int(self.raw["audio"]["sample_rate_hz"])

    @property
    def max_concurrency(self) -> int:
        return min(int(self.raw["benchmark"]["max_concurrency"]), 2)

    @property
    def websocket_connection_spacing(self) -> float:
        return float(
            self.raw["benchmark"].get("websocket_connection_spacing_s", 0.35)
        )

    @property
    def retry_attempts(self) -> int:
        return int(self.raw["benchmark"]["retries"]["attempts"])

    @property
    def retry_base_delay(self) -> float:
        return float(self.raw["benchmark"]["retries"]["base_delay_s"])

    @property
    def retry_max_delay(self) -> float:
        return float(self.raw["benchmark"]["retries"]["max_delay_s"])

    @property
    def sarvam_api_key(self) -> str:
        return _env(self.raw["environment"]["sarvam_api_key"])

    @property
    def sarvam_ws_url(self) -> str:
        return _env(
            self.raw["environment"]["sarvam_ws_url"],
            "wss://api.sarvam.ai",
        ).rstrip("/")

    @property
    def llm_api_key(self) -> str:
        return _env(self.raw["environment"]["llm_api_key"])

    @property
    def llm_base_url(self) -> str:
        name = self.raw["environment"]["llm_base_url"]
        return _env(name, self.llm.base_url).rstrip("/")

    @property
    def llm_model(self) -> str:
        name = self.raw["environment"]["llm_model"]
        return _env(name, self.llm.model)

    @property
    def whisper_api_key(self) -> str:
        return _env(self.raw["environment"]["whisper_api_key"])

    @property
    def whisper_base_url(self) -> str:
        return _env(
            self.raw["environment"]["whisper_base_url"],
            self.whisper["base_url"],
        ).rstrip("/")

    @property
    def whisper_enabled(self) -> bool:
        requested = os.getenv("WHISPER_ENABLED", "").strip().lower()
        if requested:
            return requested in {"1", "true", "yes", "on"}
        return bool(self.whisper.get("enabled"))

    @property
    def gnani_api_key(self) -> str:
        return _env(self.raw["environment"]["gnani_api_key"])

    @property
    def network_region(self) -> str:
        return _env(
            self.raw["environment"]["network_region"],
            "Asia/Kolkata local machine timezone",
        )

    def _provider(self, name: str) -> ProviderConfig:
        raw = self.raw["providers"][name]
        return ProviderConfig(
            provider=str(raw["provider"]),
            model=str(raw["model"]),
            base_url=str(raw["base_url"]),
            temperature=float(raw["temperature"]),
            max_tokens=int(raw["max_tokens"]),
            timeout_s=float(raw["timeout_s"]),
            thinking=(
                str(raw["thinking"]).strip()
                if raw.get("thinking") is not None
                else None
            ),
        )


def load_config(path: Path | None = None) -> BenchmarkConfig:
    config_path = path or CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"{config_path} must contain a YAML mapping")
    return BenchmarkConfig(raw=raw, root=ROOT)


__all__ = ["API_ROOT", "BenchmarkConfig", "ProviderConfig", "ROOT", "load_config"]
