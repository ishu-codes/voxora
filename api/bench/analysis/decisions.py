"""Apply the prompt selection rule from recorded training results."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from bench.core.config import ROOT
from bench.utils.results import read_json


def _version_rows(root: Path) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted((root / "results" / "scenarios").glob("scenario-v*-run*.json")):
        result = read_json(path)
        grouped[result["prompt_version"]].append(result)
    return grouped


def _category_rates(results: list[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[bool]] = defaultdict(list)
    for result in results:
        grouped[result["scenario"]["category"]].append(bool(result["pass"]))
    return {
        category: sum(values) / len(values)
        for category, values in grouped.items()
    }


def generate(root: Path = ROOT) -> str:
    grouped = _version_rows(root)
    rates = {
        version: _category_rates(results)
        for version, results in grouped.items()
    }
    comparison: list[dict[str, Any]] = []
    for version, results in sorted(grouped.items()):
        pass_count = sum(bool(result["pass"]) for result in results)
        inconsistent = 0
        by_scenario: dict[str, list[bool]] = defaultdict(list)
        for result in results:
            by_scenario[result["scenario"]["id"]].append(bool(result["pass"]))
        inconsistent = sum(len(set(values)) > 1 for values in by_scenario.values())
        lost_categories = 0
        for category, rate in rates[version].items():
            other_hit_100 = any(
                other != version and other_rates.get(category) == 1.0
                for other, other_rates in rates.items()
            )
            if rate < 1.0 and other_hit_100:
                lost_categories += 1
        comparison.append(
            {
                "version": version,
                "runs": len(results),
                "passed": pass_count,
                "pass_rate": pass_count / len(results),
                "categories_lost_to_100pct_versions": lost_categories,
                "inconsistent_scenarios": inconsistent,
            }
        )
    chosen = min(
        comparison,
        key=lambda item: (
            -item["pass_rate"],
            item["categories_lost_to_100pct_versions"],
            item["inconsistent_scenarios"],
            item["version"],
        ),
    )["version"]
    shutil.copyfile(
        root / "prompts" / f"agent_{chosen}.txt",
        root / "prompts" / "agent_final.txt",
    )
    lines = [
        "# Prompt decision",
        "",
        "These 20 scenarios were used to write the prompts. The selected score is a training score, not a held-out score.",
        "",
        "| Version | Runs | Passed | Pass rate | Categories lost to a 100% version | Inconsistent scenarios |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in comparison:
        lines.append(
            f"| {item['version']} | {item['runs']} | {item['passed']} | "
            f"{item['pass_rate']:.1%} | "
            f"{item['categories_lost_to_100pct_versions']} | "
            f"{item['inconsistent_scenarios']} |"
        )
    lines.extend(
        [
            "",
            (f"Selected version: **{chosen}**. The selection applies the specified "
            "order: highest overall pass rate, then fewest categories another "
            "version passed completely, then fewest inconsistent scenarios. An "
            "exact remaining tie is resolved by choosing the earlier version "
            "identifier, which is the documented deterministic tie-break."),
            "",
            f"`prompts/agent_final.txt` is copied from `prompts/agent_{chosen}.txt`.",
        ]
    )
    (root / "DECISIONS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"chosen": chosen, "comparison": comparison}, indent=2))
    return chosen


if __name__ == "__main__":
    generate()
