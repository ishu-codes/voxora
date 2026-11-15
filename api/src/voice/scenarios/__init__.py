"""Load scenario definitions stored beside the voice application."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

SCENARIO_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    description: str
    language_hint: str
    system_prompt: str
    opening_line: str
    voice: str
    outbound: bool

    def public(self) -> dict[str, Any]:
        return asdict(self)


@lru_cache(maxsize=1)
def load_scenarios(directory: Path | str = SCENARIO_DIR) -> dict[str, Scenario]:
    root = Path(directory)
    scenarios: dict[str, Scenario] = {}
    for path in sorted(root.glob("*.toml")):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ValueError(f"Unable to load scenario {path}: {exc}") from exc
        required = (
            "id",
            "title",
            "language_hint",
            "system_prompt",
            "opening_line",
            "voice",
        )
        missing = [key for key in required if not str(data.get(key, "")).strip()]
        if missing:
            raise ValueError(f"{path} is missing: {', '.join(missing)}")
        scenario = Scenario(
            id=str(data["id"]).strip(),
            title=str(data["title"]).strip(),
            description=str(data.get("description", "")).strip(),
            language_hint=str(data["language_hint"]).strip(),
            system_prompt=str(data["system_prompt"]).strip(),
            opening_line=str(data["opening_line"]).strip(),
            voice=str(data["voice"]).strip(),
            outbound=bool(data.get("outbound", False)),
        )
        if scenario.id in scenarios:
            raise ValueError(f"Duplicate scenario id: {scenario.id}")
        scenarios[scenario.id] = scenario
    if not scenarios:
        raise ValueError(f"No scenario files found in {root}")
    return scenarios


def get_scenario(scenario_id: str) -> Scenario:
    scenarios = load_scenarios()
    try:
        return scenarios[scenario_id]
    except KeyError as exc:
        raise KeyError(f"Unknown scenario {scenario_id!r}") from exc


def public_scenarios() -> list[dict[str, Any]]:
    preferred = ("kirana", "pizza", "emi-reminder")
    scenarios = load_scenarios()
    ordered = [scenarios[key] for key in preferred if key in scenarios]
    ordered.extend(
        scenario for scenario in scenarios.values() if scenario.id not in preferred
    )
    return [scenario.public() for scenario in ordered]


__all__ = [
    "SCENARIO_DIR",
    "Scenario",
    "get_scenario",
    "load_scenarios",
    "public_scenarios",
]
