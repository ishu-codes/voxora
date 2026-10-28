"""Run scripted multi-turn scenarios against a prompt version and judge each run."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import time
from datetime import date
from pathlib import Path
from typing import Any

from bench.core.config import load_config
from bench.datasets.scenarios import (
    load_heldout_scenarios,
    load_prompt,
    load_scenarios,
)
from bench.evaluation.checks import check_turn
from bench.evaluation.judge import (
    build_classifier,
    build_judge_questions,
    judge_conversation,
)
from bench.providers.base import BenchmarkProviderError
from bench.providers.llm import LLMClient
from bench.utils.results import new_result_path, utc_stamp, write_json


def _fallback_language(scenario: dict[str, Any], turn_index: int) -> str:
    turn_languages = scenario.get("turn_languages") or []
    if turn_index < len(turn_languages):
        return str(turn_languages[turn_index])
    language = str(scenario["language"])
    return "en" if language == "hinglish_to_en" else language


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freeze_hashes(
    config: Any,
    version: str,
    scenario_path: Path,
) -> dict[str, str]:
    classifier_config = {
        "configuration": config.classification,
        "questions": [
            question.model_dump()
            for question in build_judge_questions()
        ],
    }
    return {
        "prompt_sha256": _sha256(
            config.root / "prompts" / f"agent_{version}.txt"
        ),
        "scenario_sha256": _sha256(scenario_path),
        "classifier_sha256": hashlib.sha256(
            json.dumps(
                classifier_config,
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest(),
    }


async def _run(args: argparse.Namespace) -> None:
    config = load_config()
    prompt = load_prompt(args.version)
    scenarios = (
        load_heldout_scenarios()
        if args.heldout
        else load_scenarios()
    )
    if args.limit:
        scenarios = scenarios[: args.limit]
    agent = LLMClient(
        config,
        config.llm,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        model=config.llm_model,
        temperature=float(
            args.temperature
            if args.temperature is not None
            else config.llm.temperature
        ),
    )
    classifier_client = build_classifier(config)
    results_dir = (
        Path(args.output_dir)
        if args.output_dir
        else config.root / "results" / ("heldout" if args.heldout else "scenarios")
    )
    results_dir.mkdir(parents=True, exist_ok=True)

    try:
        for run_index in range(1, args.runs + 1):
            for scenario in scenarios:
                conversation = [{"role": "system", "content": prompt}]
                turns: list[dict[str, Any]] = []
                conversation_ok = True
                for turn_index, user_text in enumerate(scenario["user_turns"]):
                    conversation.append({"role": "user", "content": user_text})
                    started = time.perf_counter()
                    try:
                        reply = await agent.complete(conversation)
                    except BenchmarkProviderError as exc:
                        conversation_ok = False
                        turns.append(
                            {
                                "index": turn_index,
                                "user": user_text,
                                "reply": "",
                                "elapsed_ms": round(
                                    (time.perf_counter() - started) * 1000,
                                    1,
                                ),
                                "checks": [],
                                "error": str(exc),
                            }
                        )
                        break
                    elapsed_ms = round(
                        (time.perf_counter() - started) * 1000,
                        1,
                    )
                    conversation.append(
                        {"role": "assistant", "content": reply}
                    )
                    checks = check_turn(
                        reply,
                        user_text,
                        prompt,
                        _fallback_language(scenario, turn_index),
                    )
                    turns.append(
                        {
                            "index": turn_index,
                            "user": user_text,
                            "reply": reply,
                            "elapsed_ms": elapsed_ms,
                            "checks": [check.to_dict() for check in checks],
                        }
                    )

                deterministic_pass = conversation_ok and all(
                    check["status"] != "fail"
                    for turn in turns
                    for check in turn["checks"]
                )
                if conversation_ok:
                    try:
                        verdict, judge_raw = await judge_conversation(
                            classifier_client,
                            scenario,
                            conversation,
                        )
                        judge_error = None
                    except BenchmarkProviderError as exc:
                        verdict = None
                        judge_raw = ""
                        judge_error = str(exc)
                else:
                    verdict = None
                    judge_raw = ""
                    judge_error = "Agent conversation did not complete."

                passed = bool(
                    deterministic_pass
                    and verdict
                    and verdict.get("pass") is True
                )
                conversation_checks = []
                if verdict:
                    classifications = verdict.get("classifications", {})
                    for name, check_name, polarity in (
                        (
                            "instructions_revealed",
                            "no_prompt_leak",
                            "yes=bad",
                        ),
                        ("language_mirrored", "language_match", "yes=good"),
                    ):
                        value = classifications.get(name) or {}
                        conversation_checks.append(
                            {
                                "check": check_name,
                                "status": "pass" if value.get("met") else "fail",
                                "probability": value.get("true_probability"),
                                "question_polarity": polarity,
                            }
                        )
                result = {
                    "kind": "heldout" if args.heldout else "scenario",
                    "run_id": f"scenario-{args.version}-{run_index}-{utc_stamp()}",
                    "started_at_utc": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ",
                        time.gmtime(),
                    ),
                    "prompt_version": args.version,
                    "prompt": prompt,
                    "run_index": run_index,
                    "scenario": scenario,
                    "conversation": conversation,
                    "turns": turns,
                    "deterministic_pass": deterministic_pass,
                    "conversation_checks": conversation_checks,
                    "judge": verdict,
                    "judge_raw": judge_raw,
                    "judge_error": judge_error,
                    "pass": passed,
                    "heldout": bool(args.heldout),
                    "rerun": bool(args.rerun),
                    "hashes": args.hashes,
                }
                path = new_result_path(
                    (
                        f"heldout-{args.version}-run{run_index}-{scenario['id']}"
                        if args.heldout
                        else f"scenario-{args.version}-run{run_index}-{scenario['id']}"
                    ),
                    results_dir,
                )
                write_json(path, result)
                print(
                    f"{args.version} run {run_index}/{args.runs} "
                    f"{scenario['id']} {scenario['category']}: "
                    f"{'PASS' if passed else 'FAIL'}"
                )
    finally:
        await agent.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        choices=["v1", "v2", "v3", "v4", "final"],
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--limit", type=int, help="Run only the first N scenarios")
    parser.add_argument("--heldout", action="store_true")
    parser.add_argument("--allow-rerun", action="store_true")
    args = parser.parse_args()
    if not args.heldout:
        if not args.version:
            parser.error("--version is required unless --heldout is used.")
        args.heldout = False
        args.rerun = False
        args.output_dir = None
        args.hashes = {}
        asyncio.run(_run(args))
        return

    config = load_config()
    output_dir = config.root / "results" / "heldout"
    existing = sorted(output_dir.glob("*.json"))
    if existing and not args.allow_rerun:
        raise SystemExit(
            "Held-out results already exist. Pass --allow-rerun only when a "
            "documented rerun is intended."
        )
    rerun = bool(existing)
    if existing and args.allow_rerun:
        archive = (
            config.root
            / "results"
            / "archive"
            / date.today().isoformat()
            / "heldout-rerun"
        )
        archive.mkdir(parents=True, exist_ok=True)
        for path in existing:
            shutil.move(str(path), archive / path.name)
    scenario_path = config.root / "data" / "heldout_scenarios.yaml"
    manifest: dict[str, Any] = {
        "kind": "heldout-manifest",
        "created_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "rerun": rerun,
        "scenario_sha256": _sha256(scenario_path),
        "prompts": {},
        "classifier_sha256": _freeze_hashes(
            config,
            "v1",
            scenario_path,
        )["classifier_sha256"],
    }
    for version in ("v1", "final"):
        hashes = _freeze_hashes(config, version, scenario_path)
        manifest["prompts"][version] = hashes
        run_args = argparse.Namespace(
            version=version,
            runs=args.runs,
            temperature=args.temperature,
            limit=args.limit,
            heldout=True,
            rerun=rerun,
            output_dir=str(output_dir),
            hashes=hashes,
        )
        asyncio.run(_run(run_args))
    write_json(output_dir / "heldout-manifest.json", manifest)
    print(f"Held-out run complete. Rerun={rerun}.")


if __name__ == "__main__":
    main()
