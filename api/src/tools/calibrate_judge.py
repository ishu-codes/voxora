"""Resumable manual calibration for conversation and STT classifier labels."""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bench.core.config import API_ROOT, ROOT
from bench.evaluation.judge import FACTS
from bench.utils.results import read_json, write_json


def _conversation_candidates(results_dir: Path) -> list[dict[str, Any]]:
    final_version = "v4"
    decisions = results_dir.parent / "DECISIONS.md"
    if not decisions.exists():
        decisions = API_ROOT / "DECISIONS.md"
    if decisions.exists():
        text = decisions.read_text(encoding="utf-8")
        marker = "Selected version: **"
        if marker in text:
            final_version = text.split(marker, 1)[1].split("**", 1)[0]
    rows = []
    for path in sorted(
        (results_dir / "scenarios").glob(
            f"scenario-{final_version}-run*.json"
        )
    ):
        result = read_json(path)
        result["_key"] = f"scenario:{path.name}"
        rows.append(result)
    return rows


def _latest_clean_stt(results_dir: Path) -> dict[str, Any] | None:
    for path in sorted(results_dir.glob("stt-*.json"), reverse=True):
        payload = read_json(path)
        if payload.get("condition", "clean") == "clean":
            return payload
    return None


def _stratified(
    candidates: list[dict[str, Any]],
    size: int,
    bucket_key: Any,
    rng: random.Random,
) -> list[dict[str, Any]]:
    buckets: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        buckets[bucket_key(item)].append(item)
    for values in buckets.values():
        rng.shuffle(values)
    chosen: list[dict[str, Any]] = []
    keys = sorted(buckets, key=str)
    while len(chosen) < min(size, len(candidates)):
        progressed = False
        for key in keys:
            if buckets[key] and len(chosen) < size:
                chosen.append(buckets[key].pop())
                progressed = True
        if not progressed:
            break
    return chosen


def _ask(prompt: str) -> bool | None:
    while True:
        answer = input(prompt).strip().lower()
        if answer in {"p", "y", "true"}:
            return True
        if answer in {"f", "n", "false"}:
            return False
        if answer == "s":
            return None


def _print_facts() -> None:
    print("Call facts:")
    for key, value in FACTS.items():
        print(f"  {key}: {value}")
    print()


def _conversation_loop(
    results_dir: Path,
    count: int,
    labels: dict[str, Any],
) -> None:
    rng = random.Random(17)
    candidates = _conversation_candidates(results_dir)
    checked = {
        key
        for key, value in labels["conversations"].items()
        if value.get("human_pass") is not None
    }
    missing = [item for item in candidates if item["_key"] not in checked]
    sample = _stratified(
        missing,
        count,
        lambda item: (
            item["scenario"]["category"],
            bool(item["pass"]),
        ),
        rng,
    )
    if not sample:
        print("Conversation calibration already has a full sample.")
        return
    _print_facts()
    for index, result in enumerate(sample, 1):
        scenario = result["scenario"]
        print("=" * 78)
        print(
            f"Conversation {index}/{len(sample)}: "
            f"{scenario['id']} ({scenario['category']}, {scenario['language']})"
        )
        print("Expected:")
        for item in scenario["expected"]:
            print(f"  - {item}")
        print("Forbidden:")
        for item in scenario["forbidden"]:
            print(f"  - {item}")
        print("\nTranscript:")
        for message in result["conversation"]:
            if message["role"] != "system":
                print(f"  {message['role'].upper()}: {message['content']}")
        label = _ask("\nYour label [p]ass / [f]ail / [s]kip: ")
        if label is None:
            continue
        labels["conversations"][result["_key"]] = {
            "path": result["_key"].removeprefix("scenario:"),
            "category": scenario["category"],
            "classifier_pass": bool((result.get("judge") or {}).get("pass")),
            "deterministic_pass": bool(result.get("deterministic_pass")),
            "human_pass": label,
        }
        write_json(results_dir / "calibration" / "labels.json", labels)


def _stt_loop(
    results_dir: Path,
    count: int,
    labels: dict[str, Any],
) -> None:
    run = _latest_clean_stt(results_dir)
    if run is None:
        print("No clean STT results found.")
        return
    rng = random.Random(23)
    checked = {
        key
        for key, value in labels["stt"].items()
        if value.get("same_meaning") is not None
    }
    candidates: list[dict[str, Any]] = []
    for row in run.get("rows", []):
        key = (
            f"stt:{row['provider']}:{row['mode']}:"
            f"{row['language']}:{row['id']}"
        )
        if row.get("status") == "ok" and key not in checked:
            candidates.append({**row, "_key": key})
    sample = _stratified(
        candidates,
        count,
        lambda item: (
            item["provider"],
            item["mode"],
            item["language"],
        ),
        rng,
    )
    if not sample:
        print("STT calibration already has a full sample.")
        return
    for index, row in enumerate(sample, 1):
        print("=" * 78)
        print(
            f"STT {index}/{len(sample)}: {row['id']} "
            f"{row['provider']} / {row['mode']} / {row['language']}"
        )
        print(f"REFERENCE: {row['reference']}")
        print(f"HYPOTHESIS: {row['raw_hypothesis'] or '(empty)'}")
        label = _ask(
            "\nDo these mean the same thing? [y]es / [n]o / [s]kip: "
        )
        if label is None:
            continue
        labels["stt"][row["_key"]] = {
            "id": row["id"],
            "provider": row["provider"],
            "mode": row["mode"],
            "language": row["language"],
            "reference": row["reference"],
            "hypothesis": row["raw_hypothesis"],
            "classifier_same_meaning": row.get("semantic_match"),
            "same_meaning": label,
        }
        write_json(results_dir / "calibration" / "labels.json", labels)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conversations", type=int, default=0)
    parser.add_argument("--stt", type=int, default=0)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    if not args.conversations and not args.stt:
        parser.error("Pass --conversations N and/or --stt N.")
    path = args.results / "calibration" / "labels.json"
    labels = (
        read_json(path)
        if path.exists()
        else {"conversations": {}, "stt": {}}
    )
    labels.setdefault("conversations", {})
    labels.setdefault("stt", {})
    if args.conversations:
        _conversation_loop(args.results, args.conversations, labels)
    if args.stt:
        _stt_loop(args.results, args.stt, labels)
    write_json(path, labels)
    print(f"Saved resumable labels to {path}")


if __name__ == "__main__":
    main()
