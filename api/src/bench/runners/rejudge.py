"""Rejudge saved scenario conversations with the five-question classifier."""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path
from typing import Any

from bench.core.config import ROOT, load_config
from bench.evaluation.judge import build_classifier, judge_conversation
from bench.providers.base import BenchmarkProviderError
from bench.utils.results import read_json, write_json


def _result_files(results_dir: Path) -> list[Path]:
    return sorted((results_dir / "scenarios").glob("scenario-v*-run*.json"))


async def _run(args: argparse.Namespace) -> None:
    results_dir = args.results
    output_dir = args.output
    files = _result_files(results_dir)
    if args.version:
        files = [
            path
            for path in files
            if f"scenario-{args.version}-" in path.name
        ]
    if args.limit:
        files = files[: args.limit]
    if args.failed_only:
        files = [
            path
            for path in files
            if not read_json(path).get("pass")
            or bool(read_json(path).get("judge_error"))
        ]
    if not files:
        raise SystemExit("No matching scenario result files found.")
    output_dir.mkdir(parents=True, exist_ok=True)
    classifier_client = build_classifier(load_config())

    failures = 0
    for index, path in enumerate(files, 1):
        result: dict[str, Any] = read_json(path)
        scenario = result["scenario"]
        conversation = result["conversation"]
        record = dict(result)
        record["judge_previous"] = result.get("judge")
        record["judge_method"] = "classifier"
        record["classified_at_utc"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        )
        record["source_result"] = str(path.relative_to(results_dir))
        try:
            verdict, raw = await judge_conversation(
                classifier_client,
                scenario,
                conversation,
            )
            record["judge"] = verdict
            record["judge_raw"] = raw
            record["judge_error"] = None
            classifications = verdict.get("classifications", {})
            record["conversation_checks"] = [
                {
                    "check": check_name,
                    "status": (
                        "pass"
                        if (classifications.get(question) or {}).get("met")
                        else "fail"
                    ),
                    "probability": (
                        classifications.get(question) or {}
                    ).get("true_probability"),
                    "question_polarity": polarity,
                }
                for question, check_name, polarity in (
                    (
                        "instructions_revealed",
                        "no_prompt_leak",
                        "yes=bad",
                    ),
                    ("language_mirrored", "language_match", "yes=good"),
                )
            ]
            record["pass"] = bool(
                result.get("deterministic_pass")
                and verdict.get("pass") is True
            )
        except BenchmarkProviderError as exc:
            failures += 1
            record["judge"] = None
            record["judge_raw"] = ""
            record["judge_error"] = str(exc)
            record["pass"] = False
        output = output_dir / path.name
        write_json(output, record)
        print(
            f"{index:>3}/{len(files)} {scenario['id']} "
            f"{result['prompt_version']} run {result['run_index']}: "
            f"{'PASS' if record['pass'] else 'FAIL'}"
            + (f" ({record['judge_error']})" if record["judge_error"] else "")
        )

    print(f"Classifier rejudge wrote {len(files)} files to {output_dir}")
    print(f"Classifier request failures: {failures}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=ROOT / "results",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "scenarios-classifier",
    )
    parser.add_argument("--version", choices=["v1", "v2", "v3", "v4", "final"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--failed-only", action="store_true")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
