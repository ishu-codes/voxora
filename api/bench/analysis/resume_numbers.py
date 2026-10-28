"""Generate RESUME_NUMBERS.md from raw result JSON files."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from bench.analysis.report import percentile
from bench.core.config import ROOT
from bench.utils.results import read_json


def _latest(results_dir: Path, prefix: str) -> dict[str, Any] | None:
    files = sorted(results_dir.glob(f"{prefix}-*.json"))
    return read_json(files[-1]) if files else None


def _stt_headline(results_dir: Path) -> dict[str, str]:
    run = None
    for path in sorted(results_dir.glob("stt-*.json"), reverse=True):
        payload = read_json(path)
        if payload.get("condition", "clean") == "clean":
            run = payload
            break
    if run is None:
        return {}
    best_path = results_dir / "stt_best.json"
    best = (
        read_json(best_path).get("languages", {})
        if best_path.exists()
        else {}
    )
    values: dict[str, str] = {}
    for language in ("en", "hi", "hinglish"):
        selection = best.get(language)
        if not selection:
            values[language] = "not available"
            continue
        selected = [
            row
            for row in run.get("rows", [])
            if row.get("condition", "clean") == "clean"
            and row["language"] == language
            and row["provider"] == selection["provider"]
            and row["mode"] == selection["mode"]
            and row["status"] == "ok"
        ]
        wers = [
            float(row["wer"])
            for row in selected
            if row.get("wer_comparable") and row.get("wer") is not None
        ]
        semantic = [
            bool(row.get("semantic_match"))
            for row in selected
            if row.get("semantic_match") is not None
        ]
        entities = [
            bool(check.get("matched"))
            for row in selected
            for check in row.get("entity_checks", [])
        ]
        values[f"{language}_wer"] = (
            f"{statistics.fmean(wers) * 100:.1f}%"
            if wers
            else "not available"
        )
        values[f"{language}_semantic"] = (
            f"{sum(semantic) / len(semantic) * 100:.1f}%"
            if semantic
            else "not available"
        )
        values[f"{language}_entity"] = (
            f"{sum(entities) / len(entities) * 100:.1f}%"
            if entities
            else "not available"
        )
    return values


def generate(root: Path = ROOT) -> None:
    results = root / "results"
    stt = _stt_headline(results)
    latency = _latest(results, "latency") or {}
    latency_rows = [
        float(row["end_to_end_ms"])
        for row in latency.get("rows", [])
        if row.get("status") == "ok" and row.get("end_to_end_ms") is not None
    ]
    scenario_results: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in (results / "scenarios").glob("scenario-v*-run*.json"):
        payload = read_json(path)
        scenario_results[payload["prompt_version"]].append(payload)
    final_version = "v3"
    decisions = root / "DECISIONS.md"
    if decisions.exists():
        text = decisions.read_text(encoding="utf-8")
        marker = "Selected version: **"
        if marker in text:
            final_version = text.split(marker, 1)[1].split("**", 1)[0]

    def pass_rate(version: str) -> str:
        rows = scenario_results.get(version, [])
        return (
            f"{sum(bool(row['pass']) for row in rows)}/{len(rows)} "
            f"({sum(bool(row['pass']) for row in rows) / len(rows) * 100:.1f}%)"
            if rows
            else "not available"
        )

    heldout_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in (results / "heldout").glob("heldout-*.json"):
        payload = read_json(path)
        if payload.get("kind") != "heldout":
            continue
        heldout_groups[payload["prompt_version"]].append(payload)
    heldout_values: dict[str, str] = {}
    for version, values in heldout_groups.items():
        passed = sum(bool(item["pass"]) for item in values)
        heldout_values[version] = (
            f"{passed}/{len(values)} ({passed / len(values) * 100:.1f}%)"
        )
    labels = results / "calibration" / "final.json"
    agreement = "not available"
    if labels.exists():
        payload = read_json(labels)
        overall = payload.get("overall", {})
        if overall.get("agreement") is not None:
            agreement = f"{float(overall['agreement']) * 100:.1f}%"

    rows = [
        ["English comparable WER", stt.get("en_wer", "not available"), "REPORT.md STT table"],
        ["Hindi comparable WER", stt.get("hi_wer", "not available"), "REPORT.md STT table"],
        ["Hinglish semantic accuracy", stt.get("hinglish_semantic", "not available"), "REPORT.md STT table"],
        ["Hinglish entity accuracy", stt.get("hinglish_entity", "not available"), "REPORT.md STT table"],
        ["Latency p50", f"{percentile(latency_rows, 0.50):.1f} ms" if latency_rows else "not available", "REPORT.md latency table"],
        ["Latency p95", f"{percentile(latency_rows, 0.95):.1f} ms" if latency_rows else "not available", "REPORT.md latency table"],
        ["Training pass, v1", pass_rate("v1"), "REPORT.md scenario table"],
        [f"Training pass, final ({final_version})", pass_rate(final_version), "REPORT.md scenario table"],
        ["Held-out pass, v1", heldout_values.get("v1", "not available"), "REPORT.md held-out table"],
        [
            "Held-out pass, final",
            heldout_values.get(
                "final",
                heldout_values.get(final_version, "not available"),
            ),
            "REPORT.md held-out table",
        ],
        ["Classifier agreement", agreement, "REPORT.md calibration table"],
    ]
    lines = [
        "# Resume numbers",
        "",
        "| Headline | Value | Source |",
        "| --- | ---: | --- |",
    ]
    lines.extend(f"| {name} | {value} | {source} |" for name, value, source in rows)
    (root / "RESUME_NUMBERS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"values": rows}, indent=2))


if __name__ == "__main__":
    generate()
