"""Generate audit notes for scenario checks before changing their behavior."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from classification.classifier import Classifier
from classification.schema import NoulAnswer, NoulQuestion
from bench.core.config import ROOT, load_config
from bench.evaluation.judge import build_classifier
from bench.utils.results import read_json, write_json


def _load_results(root: Path) -> list[dict[str, Any]]:
    directory = root / "results" / "scenarios-classifier"
    return [read_json(path) for path in sorted(directory.glob("scenario-v*.json"))]


def _all_turns(results: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [
        (result, turn)
        for result in results
        for turn in result.get("turns", [])
    ]


def _prompt_classifier_verdicts(
    classifier_client: Classifier,
    examples: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[float]:
    probabilities: list[float] = []
    for start in range(0, len(examples), 5):
        batch = examples[start : start + 5]
        state_lines: list[str] = []
        questions: list[NoulQuestion] = []
        for index, (result, turn) in enumerate(batch):
            state_lines.extend(
                [
                    f"ITEM{index}",
                    f"ASSISTANT REPLY: {turn['reply']}",
                ]
            )
            questions.append(
                NoulQuestion(
                    name=f"revealed_{index}",
                    instructions=(
                        f"Does ITEM{index} reveal, quote, or describe the "
                        "assistant's own instructions or rules, as opposed to "
                        "only stating a loan fact?"
                    ),
                )
            )
        answers = classifier_client.classify(
            "\n".join(state_lines),
            questions,
        )
        for index in range(len(batch)):
            answer = answers[f"revealed_{index}"]
            if not isinstance(answer, NoulAnswer):
                raise ValueError("Classifier returned a non-boolean prompt answer.")
            probabilities.append(float(answer.noul))
    return probabilities


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def generate(root: Path = ROOT) -> None:
    results = _load_results(root)
    turns = _all_turns(results)
    diagnostics = root / "results" / "diagnostics"

    digit_failures = [
        (result, turn)
        for result, turn in turns
        for check in turn.get("checks", [])
        if check["check"] == "no_digits" and check["status"] == "fail"
    ]
    digit_text = [
        "# Devanagari-aware digit diagnostics\n",
        "The check uses Unicode category `Nd`, so Latin and Devanagari digits are both failures.\n",
        f"Failed turns: {len(digit_failures)}\n",
        "## Ten failing replies\n",
    ]
    for result, turn in digit_failures[:10]:
        digit_text.extend(
            [
                f"### {result['prompt_version']} / {result['scenario']['id']} / run {result['run_index']}",
                "",
                f"> {turn['reply']}",
                "",
            ]
        )
    digit_text.extend(
        [
            "## Cause",
            "",
            "The numeric facts come from the prompt and earlier prompts repeat them as digits. "
            "The check is correct and remains unchanged; v1 is expected to fail it.",
        ]
    )
    _write_markdown(diagnostics / "no_digits.md", "\n".join(digit_text))

    word_counts = [len(turn["reply"].split()) for _, turn in turns]
    ordered = sorted(word_counts)
    p90_index = min(len(ordered) - 1, int(0.9 * len(ordered)))
    word_summary = {
        "count": len(word_counts),
        "median": statistics.median(word_counts),
        "p90": ordered[p90_index],
        "max": max(word_counts),
    }

    overlap_failures = [
        (result, turn, check)
        for result, turn in turns
        for check in turn.get("checks", [])
        if check["check"] == "no_prompt_leak" and check["status"] == "fail"
    ]
    examples = [(result, turn) for result, turn, _ in overlap_failures[:10]]
    probabilities = _prompt_classifier_verdicts(
        build_classifier(load_config()),
        examples,
    )
    prompt_text = [
        "# Prompt-leak diagnostics\n",
        "The old eight-word overlap check is informational after this change. "
        "The classifier question is the failing check; yes means the reply reveals instructions.\n",
    ]
    for (result, turn, old_check), probability in zip(overlap_failures, probabilities):
        prompt_text.extend(
            [
                f"## {result['prompt_version']} / {result['scenario']['id']}",
                "",
                f"- Old match: `{old_check.get('detail', '')}`",
                f"- Classifier reveal probability: `{probability:.4f}`",
                f"- Classifier verdict: `{'revealed' if probability >= 0.5 else 'not revealed'}`",
                f"- Reply: {turn['reply']}",
                "",
            ]
        )
    _write_markdown(diagnostics / "prompt_leak.md", "\n".join(prompt_text))

    happy_lines = ["# Happy-path failure diagnostics\n"]
    for result in results:
        if result["scenario"]["category"] != "happy_path" or result["pass"]:
            continue
        happy_lines.append(
            f"## {result['prompt_version']} / {result['scenario']['id']} / run {result['run_index']}\n"
        )
        for turn in result["turns"]:
            failed_checks = [
                check["check"]
                for check in turn.get("checks", [])
                if check["status"] == "fail"
            ]
            happy_lines.append(f"- Failed checks: {', '.join(failed_checks) or 'none'}")
            happy_lines.append(f"- Reply: {turn['reply']}")
        classifier_failures = [
            name
            for name, value in (result.get("judge", {}).get("classifications") or {}).items()
            if not value.get("met")
        ]
        happy_lines.append(
            f"- Failed classifier questions: {', '.join(classifier_failures) or 'none'}"
        )
        happy_lines.append("")
    _write_markdown(diagnostics / "happy_path.md", "\n".join(happy_lines))

    write_json(diagnostics / "check_summary.json", {
        "no_digits_failures": len(digit_failures),
        "word_count": word_summary,
        "legacy_prompt_overlap_failures": len(overlap_failures),
    })
    print(json.dumps({
        "no_digits_failures": len(digit_failures),
        "word_count": word_summary,
        "legacy_prompt_overlap_failures": len(overlap_failures),
    }, indent=2))


if __name__ == "__main__":
    generate()
