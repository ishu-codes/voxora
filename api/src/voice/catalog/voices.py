"""Runtime access to the Sarvam and Gnani voice catalogs."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).with_name("voices.json")
GNANI_CATALOG_PATH = Path(__file__).with_name("gnani_voices.json")
Catalog = dict[str, Any]


@lru_cache(maxsize=2)
def load_catalog(path: Path | str = CATALOG_PATH) -> Catalog:
    """Load the JSON catalog once per process."""
    catalog_path = Path(path)
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Unable to load voice catalog: {catalog_path}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("models"), dict):
        raise TypeError(f"{catalog_path} must contain a models object")
    return data


def _voices_for_model(catalog: Catalog, model: str) -> list[dict[str, str]]:
    models = catalog["models"]
    for model_name, model_data in models.items():
        if model_name.lower() in model.lower():
            voices = model_data.get("voices") if isinstance(model_data, dict) else None
            if isinstance(voices, list) and voices:
                return voices
    default_model = catalog.get("default_model")
    model_data = models.get(default_model)
    voices = model_data.get("voices") if isinstance(model_data, dict) else None
    if not isinstance(voices, list) or not voices:
        raise ValueError("Voice catalog has no default model voices")
    return voices


def build_catalog(
    model: str,
    default_voice: str,
    provider: str = "sarvam",
) -> dict[str, object]:
    """Build the browser response for one configured provider and model."""
    data = load_catalog(GNANI_CATALOG_PATH if provider == "gnani" else CATALOG_PATH)
    voices = _voices_for_model(data, model)
    known = {voice["id"] for voice in voices}
    return {
        "provider": data["provider"],
        "kind": data["kind"],
        "model": model,
        "default_voice": default_voice if default_voice in known else voices[0]["id"],
        "languages": data["languages"],
        "voices": voices,
        "cache_ttl_seconds": data["cache_ttl_seconds"],
    }


__all__ = ["CATALOG_PATH", "GNANI_CATALOG_PATH", "build_catalog", "load_catalog"]
