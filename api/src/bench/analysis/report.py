"""Generate REPORT.md exclusively from raw files under results/."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from bench.analysis.calibration import summarize as summarize_calibration
from bench.core.config import API_ROOT, ROOT
from bench.utils.results import read_json

LATENCY_FIELDS = (
    "stt_first_partial_ms",
    "stt_final_ms",
    "llm_first_token_ms",
    "tts_first_audio_ms",
    "end_to_end_ms",
)


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _pct(value: float | None) -> str:
    return "not run" if value is None else f"{value * 100:.1f}%"


def _ms(value: float | None) -> str:
    return "not run" if value is None else f"{value:.1f}"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_Not run._"
    escaped_headers = [str(header) for header in headers]
    lines = [
        "| " + " | ".join(escaped_headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(str(cell).replace("|", "\\|") for cell in row)
            + " |"
        )
    return "\n".join(lines)


def _load_kind(results_dir: Path, kind: str) -> list[dict[str, Any]]:
    files = sorted(results_dir.glob(f"{kind}-*.json"))
    runs: list[dict[str, Any]] = []
    for path in files:
        if path.name.startswith(f"{kind}-run") or path.name.startswith(
            f"{kind}-v"
        ):
            continue
        payload = read_json(path)
        if payload.get("kind") == kind:
            payload["_path"] = path.name
            runs.append(payload)
    return runs


def _stt_section(results_dir: Path) -> str:
    runs = _load_kind(results_dir, "stt")
    rows = [row for run in runs for row in run.get("rows", [])]
    if not rows:
        return "## Speech-to-text\n\n_Not run._"
    clean_rows = [row for row in rows if row.get("condition", "clean") == "clean"]

    def entity_counts(selected: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
        counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for row in selected:
            for check in row.get("entity_checks", []):
                kind = str(check.get("type"))
                counts[kind][1] += 1
                counts[kind][0] += int(bool(check.get("matched")))
        return {kind: (values[0], values[1]) for kind, values in counts.items()}

    def summarize(selected: list[dict[str, Any]]) -> dict[str, Any]:
        successful = [row for row in selected if row["status"] == "ok"]
        wers = [
            float(row["wer"])
            for row in successful
            if row.get("wer_comparable") and row.get("wer") is not None
        ]
        cers = [
            float(row["cer"])
            for row in successful
            if row.get("wer_comparable") and row.get("cer") is not None
        ]
        sem = [
            bool(row.get("semantic_match"))
            for row in successful
            if row.get("semantic_match") is not None
        ]
        entities = entity_counts(successful)
        return {
            "count": len(successful),
            "errors": len(selected) - len(successful),
            "empty": sum(bool(row.get("empty_transcript")) for row in successful),
            "comparable": len(wers),
            "mismatch": len(successful) - len(wers),
            "wer_mean": statistics.fmean(wers) if wers else None,
            "wer_median": statistics.median(wers) if wers else None,
            "cer_mean": statistics.fmean(cers) if cers else None,
            "cer_median": statistics.median(cers) if cers else None,
            "semantic": sum(sem) / len(sem) if sem else None,
            "entities": entities,
        }

    language_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in clean_rows:
        language_groups[(row["provider"], row["mode"], row["language"])].append(row)

    headers = [
        "Provider",
        "Mode",
        "Language",
        "Count",
        "Errors",
        "Empty",
        "Semantic",
        "Amount",
        "Date",
        "Name",
        "Comparable WER mean",
        "Comparable CER mean",
        "Comparable n",
        "Script mismatch",
    ]
    language_table: list[list[Any]] = []
    best_candidates: dict[str, tuple[float, float, str, str]] = {}
    for (provider, mode, language), selected in sorted(language_groups.items()):
        summary = summarize(selected)
        entities = summary["entities"]

        def entity_rate(kind: str) -> str:
            correct, total = entities.get(kind, (0, 0))
            return _pct(correct / total) if total else "not available"

        language_table.append(
            [
                provider,
                mode,
                language,
                summary["count"],
                summary["errors"],
                summary["empty"],
                _pct(summary["semantic"]),
                entity_rate("amount"),
                entity_rate("date"),
                entity_rate("name"),
                _pct(summary["wer_mean"]),
                _pct(summary["cer_mean"]),
                summary["comparable"],
                summary["mismatch"],
            ]
        )
        if summary["semantic"] is not None:
            entity_total = sum(total for _, total in entities.values())
            entity_correct = sum(correct for correct, _ in entities.values())
            entity_accuracy = entity_correct / entity_total if entity_total else 0.0
            candidate = (
                summary["semantic"],
                entity_accuracy,
                mode,
                provider,
            )
            if (
                language not in best_candidates
                or candidate[:2] > best_candidates[language][:2]
            ):
                best_candidates[language] = candidate
    best_rows = [
        [language, values[3], values[2], _pct(values[0]), _pct(values[1])]
        for language, values in sorted(best_candidates.items())
    ]

    worst_lines: list[str] = []
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in clean_rows:
        if row["status"] == "ok" and row.get("semantic_probability") is not None:
            by_provider[row["provider"]].append(row)
    for provider, selected in sorted(by_provider.items()):
        worst_lines.extend([f"### {provider}", ""])
        worst_lines.append(
            _table(
                ["Utterance", "Mode", "Reference", "Hypothesis", "Semantic probability"],
                [
                    [
                        row["id"],
                        row["mode"],
                        row["reference"],
                        row["raw_hypothesis"] or "(empty)",
                        f"{float(row['semantic_probability']):.3f}",
                    ]
                    for row in sorted(
                        selected,
                        key=lambda row: float(row["semantic_probability"]),
                    )[:5]
                ],
            )
        )
        worst_lines.append("")

    noise_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        noise_groups[
            (str(row.get("condition", "clean")), row["provider"], row["mode"])
        ].append(row)
    clean_baselines = {
        (provider, mode): summarize(selected)
        for (condition, provider, mode), selected in noise_groups.items()
        if condition == "clean"
    }
    noise_table: list[list[Any]] = []
    for (condition, provider, mode), selected in sorted(noise_groups.items()):
        summary = summarize(selected)
        baseline = clean_baselines.get((provider, mode), {})
        semantic_delta = (
            summary["semantic"] - baseline["semantic"]
            if summary["semantic"] is not None and baseline.get("semantic") is not None
            else None
        )
        wer_delta = (
            summary["wer_mean"] - baseline["wer_mean"]
            if summary["wer_mean"] is not None and baseline.get("wer_mean") is not None
            else None
        )
        all_entities = summary["entities"]
        correct = sum(value[0] for value in all_entities.values())
        total = sum(value[1] for value in all_entities.values())
        noise_table.append(
            [
                condition,
                provider,
                mode,
                summary["count"],
                summary["errors"],
                _pct(summary["semantic"]),
                _pct(correct / total if total else None),
                _pct(summary["wer_mean"]),
                _pct(semantic_delta) if semantic_delta is not None else "not available",
                _pct(wer_delta) if wer_delta is not None else "not available",
            ]
        )

    coverage_rows: list[list[Any]] = []
    providers_with_results = {row["provider"] for row in clean_rows}
    for provider in sorted(providers_with_results):
        coverage_rows.append([provider, "configured modes", "run"])
    if "openai-whisper" not in providers_with_results:
        coverage_rows.append(
            [
                "openai-whisper",
                "transcribe",
                "not run (WHISPER_API_KEY unavailable)",
            ]
        )
    return (
        "## Speech-to-text\n\n"
        "### Provider coverage\n\n"
        + _table(["Provider", "Modes", "Status"], coverage_rows)
        + "\n\n"
        "### By provider, mode, and language\n\n"
        + _table(headers, language_table)
        + "\n\n### Best provider and mode per language\n\n"
        + _table(
            ["Language", "Provider", "Mode", "Semantic", "Entity accuracy"],
            best_rows,
        )
        + "\n\n### Noise and phone conditions\n\n"
        + _table(
            [
                "Condition",
                "Provider",
                "Mode",
                "Count",
                "Errors",
                "Semantic",
                "Entity accuracy",
                "Comparable WER mean",
                "Semantic change",
                "WER change",
            ],
            noise_table,
        )
        + "\n\n### Five worst utterances per provider by semantic match\n\n"
        + "\n".join(worst_lines)
    )


def _latency_section(results_dir: Path) -> str:
    runs = _load_kind(results_dir, "latency")
    if not runs:
        return "## Latency\n\n_Not run._"
    latest = runs[-1]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_language: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    failures: Counter[str] = Counter()
    for row in latest.get("rows", []):
        combination = json.dumps(latest["provider_combination"], sort_keys=True)
        if row["status"] == "ok":
            grouped[combination].append(row)
            by_language[(combination, row["language"])].append(row)
        else:
            failures[combination] += 1
    table_rows: list[list[Any]] = []
    for combination, rows in sorted(grouped.items()):
        label = combination.replace('"', "").replace("{", "").replace("}", "")
        for field in LATENCY_FIELDS:
            values = [
                float(row[field])
                for row in rows
                if row.get(field) is not None
            ]
            table_rows.append(
                [
                    label,
                    field,
                    len(values),
                    failures[combination],
                    _ms(percentile(values, 0.50)),
                    _ms(percentile(values, 0.95)),
                    _ms(max(values) if values else None),
                ]
            )
    language_rows: list[list[Any]] = []
    for (combination, language), rows in sorted(by_language.items()):
        label = combination.replace('"', "").replace("{", "").replace("}", "")
        for field in LATENCY_FIELDS:
            values = [
                float(row[field])
                for row in rows
                if row.get(field) is not None
            ]
            language_rows.append(
                [
                    label,
                    language,
                    field,
                    len(values),
                    _ms(percentile(values, 0.50)),
                    _ms(percentile(values, 0.95)),
                    _ms(max(values) if values else None),
                ]
            )
    definitions = latest.get("timing_definitions", {})
    definition_lines = "\n".join(
        f"- `{name}`: {value}" for name, value in definitions.items()
    )
    discrepancies = latest.get("sum_difference_gt_50ms", [])
    discrepancy_table = _table(
        ["Utterance", "Repeat", "Difference ms"],
        [
            [item["id"], item["repeat"], item["difference_ms"]]
            for item in discrepancies
        ],
    )
    return (
        "## Latency\n\n"
        + f"Latest run: {latest.get('started_at_utc', 'not run')}; "
        + f"machine: {latest.get('machine', 'not recorded')}; "
        + f"region: {latest.get('network_region', 'not recorded')}; "
        + f"LLM: {latest.get('provider_combination', {}).get('llm', 'not recorded')}.\n\n"
        + "### Timing definitions\n\n"
        + definition_lines
        + "\n\n### Overall\n\n"
        + _table(
            [
                "Provider combination",
                "Field",
                "Count",
                "Failures",
                "p50 ms",
                "p95 ms",
                "Max ms",
            ],
            table_rows,
        )
        + "\n\n### By language\n\n"
        + _table(
            [
                "Provider combination",
                "Language",
                "Field",
                "Count",
                "p50 ms",
                "p95 ms",
                "Max ms",
            ],
            language_rows,
        )
        + "\n\n### Turns where stage sum differs by more than fifty milliseconds\n\n"
        + f"Count: {len(discrepancies)} of {len(latest.get('rows', []))} turns.\n\n"
        + discrepancy_table
        + "\n\nThe stage sum is `stt_final + llm_first_token + tts_first_audio`. "
        "It omits the time from the first LLM token to the first complete sentence "
        "and any scheduling or network gaps between stages. Positive differences "
        "are expected because sentence assembly is part of end-to-end latency but "
        "not part of the first-token duration."
    )


def _scenario_rows(results_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    classifier_paths = sorted(
        (results_dir / "scenarios-classifier").glob("scenario-v*-run*.json")
    )
    paths = classifier_paths or sorted(
        (results_dir / "scenarios").glob("scenario-v*-run*.json")
    )
    for path in paths:
        payload = read_json(path)
        if payload.get("kind") == "scenario":
            payload["_path"] = path.name
            rows.append(payload)
    return rows


def _scenario_section(results_dir: Path) -> tuple[str, list[dict[str, Any]]]:
    scenarios = _scenario_rows(results_dir)
    if not scenarios:
        return "## Scenarios\n\n_Not run._", scenarios
    latest_judge = scenarios[-1].get("judge") or {}
    method_note = (
        f"Judging method: {latest_judge.get('method', 'unknown')}; "
        f"model: {latest_judge.get('model', 'not recorded')}; "
        f"questions per conversation: {latest_judge.get('question_count', 'not recorded')}."
    )
    by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_category: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    incomplete: Counter[str] = Counter()
    for result in scenarios:
        version = result["prompt_version"]
        by_version[version].append(result)
        category = result["scenario"]["category"]
        by_category[(version, category)].append(result)
        incomplete[version] += int(bool(result.get("judge_error")))
    version_rows = [
        [
            version,
            len(selected),
            sum(bool(item["pass"]) for item in selected),
            _pct(
                sum(bool(item["pass"]) for item in selected) / len(selected)
            ),
            incomplete[version],
        ]
        for version, selected in sorted(by_version.items())
    ]
    category_rows = [
        [
            version,
            category,
            len(selected),
            _pct(sum(bool(item["pass"]) for item in selected) / len(selected)),
        ]
        for (version, category), selected in sorted(by_category.items())
    ]

    inconsistent = 0
    consistency_rows: list[list[Any]] = []
    for version, selected in sorted(by_version.items()):
        scenario_verdicts: dict[str, list[bool]] = defaultdict(list)
        for item in selected:
            scenario_verdicts[item["scenario"]["id"]].append(bool(item["pass"]))
        differing = [
            scenario_id
            for scenario_id, verdicts in scenario_verdicts.items()
            if len(set(verdicts)) > 1
        ]
        inconsistent += len(differing)
        consistency_rows.append(
            [version, len(differing), ", ".join(sorted(differing)) or "none"]
        )

    deterministic: Counter[str] = Counter()
    for result in scenarios:
        for turn in result.get("turns", []):
            for check in turn.get("checks", []):
                if check["status"] == "fail":
                    deterministic[check["check"]] += 1
        for check in result.get("conversation_checks", []):
            if check["status"] == "fail":
                deterministic[check["check"]] += 1
    deterministic_rows = [
        [name, count]
        for name, count in deterministic.most_common()
    ]

    failure_causes: dict[str, Counter[str]] = defaultdict(Counter)
    for result in scenarios:
        verdict = result.get("judge") or {}
        if not bool(result["pass"]):
            reason = (verdict.get("failure_reason") or "").strip()
            if not reason:
                reason = result.get("judge_error") or "Deterministic check failed"
            failure_causes[result["prompt_version"]][reason] += 1
    cause_sections: list[str] = []
    for version, counter in sorted(failure_causes.items()):
        cause_sections.append(f"### {version}")
        cause_sections.append("")
        cause_sections.append(
            _table(
                ["Failure cause", "Count"],
                [[reason, count] for reason, count in counter.most_common(8)],
            )
        )
        cause_sections.append("")

    text = (
        "## Scenarios\n\n"
        + method_note
        + "\n\nThese are **training-set** results; the 20 scenarios were used to write the prompts."
        + "\n\n"
        "### Pass rate by prompt version\n\n"
        + _table(
            ["Version", "Runs", "Passed", "Pass rate", "Judge errors"],
            version_rows,
        )
        + "\n\n### Pass rate by category\n\n"
        + _table(
            ["Version", "Category", "Runs", "Pass rate"],
            category_rows,
        )
        + "\n\n### Inconsistent scenarios\n\n"
        + _table(
            ["Version", "Inconsistent", "Scenario ids"],
            consistency_rows,
        )
        + "\n\n### Deterministic check failures\n\n"
        + _table(["Check", "Failed turns"], deterministic_rows)
        + "\n\n### Top failure causes\n\n"
        + "\n".join(cause_sections)
    )
    return text, scenarios


def _calibration_section(results_dir: Path) -> str:
    labels_path = results_dir / "calibration" / "labels.json"
    if labels_path.exists():
        summary = summarize_calibration(read_json(labels_path))
        label = "labels.json"
        status = "Current calibration sample."
    else:
        files = sorted((results_dir / "calibration").glob("round*.json"))
        if not files:
            return "## Classifier calibration\n\n_Not run._"
        summary = read_json(files[-1])
        label = files[-1].name
        status = "Previous calibration round; a fresh sample is required after classifier wording changes."
    rows = []
    for name, value in (
        ("Overall", summary["overall"]),
        ("Conversations", summary["conversations"]),
        ("STT", summary["stt"]),
    ):
        false_pass = value.get("false_pass_rate")
        false_pass_ci = value.get("false_pass_rate_ci95")
        kappa = value.get("kappa")
        kappa_ci = value.get("kappa_ci95")
        rows.append(
            [
                name,
                value.get("sample_size"),
                _pct(value.get("agreement")),
                (
                    f"{value['agreement_ci95'][0] * 100:.1f}–"
                    f"{value['agreement_ci95'][1] * 100:.1f}%"
                    if value.get("agreement_ci95")
                    else "not available"
                ),
                (
                    _pct(false_pass)
                    if false_pass is not None
                    else (
                        "not available (0 human failures)"
                        if name == "Conversations"
                        else "not available"
                    )
                ),
                (
                    f"{false_pass_ci[0] * 100:.1f}–"
                    f"{false_pass_ci[1] * 100:.1f}%"
                    if false_pass_ci
                    else "not available"
                ),
                f"{kappa:.3f}" if kappa is not None else "not available",
                (
                    f"{kappa_ci[0]:.3f}–{kappa_ci[1]:.3f}"
                    if kappa_ci
                    else "not available"
                ),
            ]
        )
    return (
        "## Classifier calibration\n\n"
        + f"{status} Source: `{label}`.\n\n"
        + _table(
            [
                "Group",
                "n",
                "Agreement",
                "Agreement 95% CI",
                "False-pass",
                "False-pass 95% CI",
                "Cohen kappa",
                "Kappa 95% CI",
            ],
            rows,
        )
    )


def _heldout_section(results_dir: Path) -> str:
    directory = results_dir / "heldout"
    files = sorted(directory.glob("heldout-*.json"))
    if not files:
        return "## Held-out test\n\n_Not run._"
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in files:
        payload = read_json(path)
        if payload.get("kind") == "heldout":
            grouped[payload["prompt_version"]].append(payload)
    rows = []
    for version, selected in sorted(grouped.items()):
        passed = sum(bool(item["pass"]) for item in selected)
        rows.append(
            [
                version,
                len(selected),
                passed,
                _pct(passed / len(selected)),
                bool(selected[-1].get("rerun")),
            ]
        )
    manifest_path = directory / "heldout-manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    hashes = [
        ["Scenarios", manifest.get("scenario_sha256", "not recorded")],
        ["Classifier", manifest.get("classifier_sha256", "not recorded")],
    ]
    for version, values in manifest.get("prompts", {}).items():
        hashes.append([f"{version} prompt", values.get("prompt_sha256")])
    return (
        "## Held-out test\n\nThis is the held-out result, separate from the training score.\n\n"
        + _table(
            ["Prompt", "Runs", "Passed", "Pass rate", "Rerun"],
            rows,
        )
        + "\n\n### Frozen hashes\n\n"
        + _table(["Artifact", "SHA-256"], hashes)
    )


def _changelog_section(results_dir: Path) -> str:
    root = results_dir.parent
    paths = [
        root / "bench" / "docs" / "CHECKS_CHANGELOG.md",
        root / "data" / "scenarios_CHANGELOG.md",
        root / "bench" / "docs" / "CLASSIFIER_CHANGELOG.md",
    ]
    blocks = []
    for path in paths:
        if path.exists():
            blocks.append(f"### {path.name}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "## Check and scenario changelogs\n\n" + (
        "\n\n".join(blocks) if blocks else "_No changelog changes._"
    )


def build_report(results_dir: Path | None = None) -> str:
    results_dir = results_dir or ROOT / "results"
    scenario_text, _ = _scenario_section(results_dir)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        "# Voice-agent benchmark report\n\n"
        f"Generated from `{results_dir.name}/` at {generated}. "
        "Every numeric result below is derived from raw JSON files in that directory.\n\n"
        + _stt_section(results_dir)
        + "\n\n"
        + _latency_section(results_dir)
        + "\n\n"
        + scenario_text
        + "\n\n"
        + _heldout_section(results_dir)
        + "\n\n"
        + _calibration_section(results_dir)
        + "\n\n"
        + _changelog_section(results_dir)
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--output", type=Path, default=API_ROOT / "REPORT.md")
    args = parser.parse_args()
    args.output.write_text(build_report(args.results), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
