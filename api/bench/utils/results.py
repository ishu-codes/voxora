"""Result file naming and JSON persistence."""

from __future__ import annotations

from datetime import datetime, UTC
import json
from pathlib import Path
from typing import Any

from bench.core.config import ROOT

RESULTS_DIR = ROOT / "results"


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def new_result_path(prefix: str, results_dir: Path = RESULTS_DIR) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir / f"{prefix}-{utc_stamp()}-{Path.cwd().name}.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def all_result_files(pattern: str, results_dir: Path = RESULTS_DIR) -> list[Path]:
    return sorted(results_dir.glob(pattern))


__all__ = [
    "RESULTS_DIR",
    "all_result_files",
    "new_result_path",
    "read_json",
    "utc_stamp",
    "write_json",
]
