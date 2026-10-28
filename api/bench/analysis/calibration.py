"""Calculate calibration agreement and uncertainty from saved labels."""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path
from typing import Any

from bench.core.config import ROOT
from bench.utils.results import read_json, write_json


def wilson(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
        / denominator
    )
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    if not pairs:
        return None
    observed = sum(a == b for a, b in pairs) / len(pairs)
    first = sum(a for a, _ in pairs) / len(pairs)
    second = sum(b for _, b in pairs) / len(pairs)
    expected = first * second + (1 - first) * (1 - second)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def _bootstrap_kappa(
    pairs: list[tuple[bool, bool]],
    seed: int = 31,
    samples: int = 10_000,
) -> list[float] | None:
    if len(pairs) < 2:
        return None
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        selected = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        value = kappa(selected)
        if value is not None:
            values.append(value)
    values.sort()
    return [
        values[int(0.025 * (len(values) - 1))],
        values[int(0.975 * (len(values) - 1))],
    ]


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    conversation_values = list(payload.get("conversations", {}).values())
    stt_values = list(payload.get("stt", {}).values())
    conversation_pairs = [
        (bool(item["classifier_pass"]), bool(item["human_pass"]))
        for item in conversation_values
        if item.get("human_pass") is not None
    ]
    stt_pairs = [
        (bool(item["classifier_same_meaning"]), bool(item["same_meaning"]))
        for item in stt_values
        if item.get("same_meaning") is not None
    ]
    all_pairs = conversation_pairs + stt_pairs

    def metrics(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
        agreement_count = sum(a == b for a, b in pairs)
        return {
            "sample_size": len(pairs),
            "agreement": agreement_count / len(pairs) if pairs else None,
            "agreement_ci95": wilson(agreement_count, len(pairs)),
            "kappa": kappa(pairs),
            "kappa_ci95": _bootstrap_kappa(pairs),
        }

    human_failures = [(a, b) for a, b in conversation_pairs if not b]
    false_passes = sum(a for a, _ in human_failures)
    return {
        "overall": metrics(all_pairs),
        "conversations": {
            **metrics(conversation_pairs),
            "human_failures": len(human_failures),
            "false_passes": false_passes,
            "false_pass_rate": (
                false_passes / len(human_failures)
                if human_failures
                else None
            ),
            "false_pass_rate_ci95": wilson(false_passes, len(human_failures)),
        },
        "stt": metrics(stt_pairs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels",
        type=Path,
        default=ROOT / "results" / "calibration" / "labels.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = summarize(read_json(args.labels))
    if args.output:
        write_json(args.output, summary)
    import json

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
