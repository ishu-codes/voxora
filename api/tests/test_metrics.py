import pytest

from src.voice.metrics import MetricsRegistry, percentile


def test_percentile_interpolates_and_handles_small_samples():
    assert percentile([], 50) is None
    assert percentile([100], 95) == 100.0
    assert percentile([0, 100], 50) == 50.0
    assert percentile(list(range(1, 101)), 95) == pytest.approx(95.05, abs=0.1)


def test_registry_summary_aggregates_stages():
    registry = MetricsRegistry(maxlen=10)
    for index, value in enumerate([100, 200, 300, 400], start=1):
        registry.record(
            {
                "turn_id": f"t{index}",
                "e2e_first_audio_ms": value,
                "llm_first_token_ms": value / 2,
            }
        )
    summary = registry.summary()
    assert summary["turns"] == 4
    assert summary["stages"]["e2e_first_audio_ms"]["p50"] == 250.0
    assert summary["stages"]["llm_first_token_ms"]["mean"] == 125.0


def test_registry_evicts_and_tracks_errors():
    registry = MetricsRegistry(maxlen=2)
    registry.record({"turn_id": "a", "total_ms": 1})
    registry.record({"turn_id": "b", "total_ms": 2, "error": "llm: x"})
    registry.record({"turn_id": "c", "total_ms": 3})
    summary = registry.summary()
    assert summary["turns"] == 2
    assert summary["errors"] == 1

    registry.merge("c", {"first_playback_ms": 90})
    snapshot = {turn["turn_id"]: turn for turn in registry.snapshot()}
    assert snapshot["c"]["first_playback_ms"] == 90
    registry.reset()
    assert registry.summary()["turns"] == 0
