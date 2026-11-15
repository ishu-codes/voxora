"""Read the latest generated PRD2 benchmark summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results" / "prd2"


def latest_benchmark() -> dict[str, Any]:
    summaries = sorted(RESULTS_DIR.glob("summary-*.json"))
    if not summaries:
        return {
            "status": "not_run",
            "message": "No benchmark summary has been generated yet.",
        }
    path = summaries[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["status"] = "ok"
    payload["summary_file"] = path.name
    return payload


__all__ = ["RESULTS_DIR", "latest_benchmark"]
