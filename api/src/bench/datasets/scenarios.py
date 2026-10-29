"""Scenario and CSV loading helpers."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from bench.core.config import ROOT


def load_utterances(root: Path = ROOT) -> list[dict[str, str]]:
    path = root / "data" / "utterances.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "id",
        "wav_path",
        "reference_text",
        "language",
        "script",
        "category",
        "entities",
    }
    if set(rows[0] if rows else {}) != required:
        raise ValueError(f"{path} must have columns: {sorted(required)}")
    return rows


def load_scenarios(root: Path = ROOT) -> list[dict[str, Any]]:
    path = root / "data" / "scenarios.yaml"
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    scenarios = raw.get("scenarios", raw) if isinstance(raw, dict) else raw
    if not isinstance(scenarios, list) or len(scenarios) != 20:
        raise ValueError(f"{path} must contain exactly 20 scenarios")
    ids = [scenario["id"] for scenario in scenarios]
    if len(set(ids)) != 20:
        raise ValueError(f"{path} contains duplicate scenario ids")
    return scenarios


def load_heldout_scenarios(root: Path = ROOT) -> list[dict[str, Any]]:
    path = root / "data" / "heldout_scenarios.yaml"
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    scenarios = raw.get("scenarios", raw) if isinstance(raw, dict) else raw
    if not isinstance(scenarios, list) or len(scenarios) != 10:
        raise ValueError(f"{path} must contain exactly 10 scenarios")
    ids = [scenario["id"] for scenario in scenarios]
    if ids != [f"h{index:02d}" for index in range(1, 11)]:
        raise ValueError(f"{path} must contain h01 through h10 in order")
    return scenarios


def load_prompt(version: str, root: Path = ROOT) -> str:
    path = root / "prompts" / f"agent_{version}.txt"
    return path.read_text(encoding="utf-8").strip()


__all__ = [
    "load_heldout_scenarios",
    "load_prompt",
    "load_scenarios",
    "load_utterances",
]
