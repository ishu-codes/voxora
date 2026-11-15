"""Shared test fixtures for the Voxora voice backend.

The pipeline has no database dependency, so the suite runs anywhere Python and
the runtime dependencies are installed.
"""

import pytest

from src.voice.providers.whisper_stt import WhisperEngine


@pytest.fixture(autouse=True)
def _quiet_env(monkeypatch):
    # Keep Settings.from_env deterministic when tests run next to a developer
    # .env file.
    for name in ("LLM_API_KEY", "SARVAM_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _fake_local_whisper(monkeypatch):
    class Pipeline:
        def __call__(self, _audio, **_kwargs):
            return {"text": ""}

    monkeypatch.setattr(
        WhisperEngine,
        "load",
        classmethod(lambda cls: cls(Pipeline(), "cpu")),
    )
