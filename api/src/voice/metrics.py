"""In-memory latency instrumentation with p50/p95/p99 summaries."""

from __future__ import annotations

from collections import OrderedDict
from statistics import mean
from threading import Lock
from typing import Any


def percentile(values: list[float], p: float) -> float | None:
    """Linear-interpolated percentile; friendly to small sample sizes."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    rank = (len(ordered) - 1) * (p / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 1)


_METRIC_KEYS = (
    "speech_duration_ms",
    "stt_ms",
    "llm_first_token_ms",
    "tts_first_audio_ms",
    "e2e_first_audio_ms",
    "total_ms",
    "first_playback_ms",
    "barge_in_ms",
)


class MetricsRegistry:
    def __init__(self, maxlen: int = 500) -> None:
        self._maxlen = maxlen
        self._turns: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = Lock()

    def record(self, metrics: dict[str, Any]) -> None:
        turn_id = str(metrics.get("turn_id") or "")
        if not turn_id:
            return
        with self._lock:
            self._turns[turn_id] = dict(metrics)
            while len(self._turns) > self._maxlen:
                self._turns.popitem(last=False)

    def merge(self, turn_id: str, updates: dict[str, Any]) -> None:
        with self._lock:
            existing = self._turns.get(turn_id)
            if existing is None:
                existing = {"turn_id": turn_id}
                self._turns[turn_id] = existing
            existing.update(updates)

    def snapshot(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._turns.values())
        return items[-limit:]

    def summary(self) -> dict[str, Any]:
        turns = self.snapshot(limit=self._maxlen)
        result: dict[str, Any] = {
            "turns": len(turns),
            "errors": sum(1 for turn in turns if turn.get("error")),
            "cancelled": sum(1 for turn in turns if turn.get("cancelled")),
            "stages": {},
        }
        stages: dict[str, Any] = {}
        for key in _METRIC_KEYS:
            values = [
                float(turn[key])
                for turn in turns
                if isinstance(turn.get(key), (int, float))
            ]
            if not values:
                continue
            stages[key] = {
                "count": len(values),
                "mean": round(mean(values), 1),
                "p50": percentile(values, 50),
                "p95": percentile(values, 95),
                "p99": percentile(values, 99),
            }
        result["stages"] = stages
        return result

    def reset(self) -> None:
        with self._lock:
            self._turns.clear()


registry = MetricsRegistry()

__all__ = ["MetricsRegistry", "registry", "percentile"]
