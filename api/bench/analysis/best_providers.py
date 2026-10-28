"""Select the best clean STT provider and mode per language."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from bench.core.config import ROOT
from bench.utils.results import read_json, write_json


def _runs(results_dir: Path) -> list[dict[str, Any]]:
    return [
        read_json(path)
        for path in sorted(results_dir.glob("stt-*.json"))
    ]


def select(results_dir: Path = ROOT / "results") -> dict[str, dict[str, Any]]:
    rows = [
        row
        for run in _runs(results_dir)
        for row in run.get("rows", [])
        if row.get("condition", "clean") == "clean" and row["status"] == "ok"
    ]
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["language"], row["provider"], row["mode"])].append(row)
    winners: dict[str, dict[str, Any]] = {}
    for (language, provider, mode), selected in grouped.items():
        semantic = [
            bool(row.get("semantic_match"))
            for row in selected
            if row.get("semantic_match") is not None
        ]
        entity_checks = [
            bool(check.get("matched"))
            for row in selected
            for check in row.get("entity_checks", [])
        ]
        score = (
            sum(semantic) / len(semantic) if semantic else -1.0,
            sum(entity_checks) / len(entity_checks) if entity_checks else -1.0,
        )
        current = winners.get(language)
        if current is None or score > (
            current["semantic_match"],
            current["entity_accuracy"],
        ):
            winners[language] = {
                "provider": provider,
                "mode": mode,
                "semantic_match": score[0],
                "entity_accuracy": score[1],
            }
    return winners


def main() -> None:
    winners = select()
    output = ROOT / "results" / "stt_best.json"
    write_json(output, {"selection_rule": "semantic match, entity accuracy tie-break", "languages": winners})
    print(json.dumps(winners, indent=2))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
