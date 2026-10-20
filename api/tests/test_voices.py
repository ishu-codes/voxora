from fastapi.testclient import TestClient

from main import app
from src.voice.config import Settings
from src.voice.router import VoiceCredentials
from src.voice.voices import build_catalog


def test_v3_catalog_contains_default_and_known_speakers():
    catalog = build_catalog("bulbul:v3", "shubh")
    ids = {voice["id"] for voice in catalog["voices"]}

    assert catalog["provider"] == "sarvam"
    assert catalog["kind"] == "audio"
    assert catalog["default_voice"] == "shubh"
    assert "shubh" in ids
    assert "anushka" not in ids
    assert len(ids) >= 30


def test_v2_catalog_uses_v2_speakers():
    catalog = build_catalog("bulbul:v2", "anushka")
    ids = {voice["id"] for voice in catalog["voices"]}

    assert catalog["default_voice"] == "anushka"
    assert ids == {
        "anushka",
        "manisha",
        "vidya",
        "arya",
        "abhilash",
        "karun",
        "hitesh",
    }


def test_unknown_default_falls_back_to_first_supported_voice():
    catalog = build_catalog("bulbul:v3", "not-a-real-speaker")
    assert catalog["default_voice"] == "shubh"


def test_byok_credentials_apply_only_supplied_fields():
    base = Settings(
        sarvam_api_key="platform-sarvam",
        llm_api_key="platform-llm",
        llm_base_url="https://api.openai.com/v1",
        llm_model="gpt-4o-mini",
    )
    credentials = VoiceCredentials(
        sarvam_api_key="user-sarvam",
        openai_api_key="user-llm",
        openai_base_url="https://example.test/v1/",
        openai_model="custom-model",
    )
    merged = credentials.apply(base)

    assert credentials.full_byok is True
    assert merged.sarvam_api_key == "user-sarvam"
    assert merged.llm_api_key == "user-llm"
    assert merged.llm_base_url == "https://example.test/v1"
    assert merged.llm_model == "custom-model"
    assert merged.llm_provider == "openai"


def test_credentials_require_http_base_url():
    try:
        VoiceCredentials.from_payload({"openai_base_url": "file:///etc/passwd"})
    except ValueError as exc:
        assert "http" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected invalid URL to be rejected")


def test_voice_catalog_endpoint_is_cacheable():
    with TestClient(app) as client:
        response = client.get("/api/v1/voice/voices")

    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("public, max-age=86400")
    payload = response.json()
    assert payload["provider"] == "sarvam"
    assert payload["voices"]


def test_websocket_accepts_byok_before_ready():
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/voice/ws") as websocket:
            websocket.send_json(
                {
                    "type": "configure",
                    "byok": {
                        "sarvam_api_key": "user-sarvam",
                        "openai_api_key": "user-llm",
                        "openai_base_url": "https://example.test/v1",
                        "openai_model": "custom-model",
                    },
                }
            )
            ready = websocket.receive_json()

    assert ready["type"] == "ready"
    assert ready["platform"] == {"limited": False, "turn_limit": None}
