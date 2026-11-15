import asyncio
from types import SimpleNamespace

import httpx

from main import app
from src.voice.catalog.voices import CATALOG_PATH, build_catalog, load_catalog
from src.voice.security.rate_limit import StrictRateLimiter
from src.voice.services.voice import handle_control_text, serve_voice_socket
from src.tests.test_rate_limit import _FakeWebSocket, _router_app, _router_settings


class _TransportStub:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def send(self, event: dict) -> None:
        self.events.append(event)


class _PipelineStub:
    def __init__(self) -> None:
        self.session = SimpleNamespace(session_id="test-session")
        self.transport = _TransportStub()
        self.interrupts: list[tuple[str, str | None]] = []

    async def interrupt(self, reason: str, turn_id: str | None = None) -> None:
        self.interrupts.append((reason, turn_id))


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


def test_catalog_loads_voice_metadata_from_json(tmp_path):
    path = tmp_path / "voices.json"
    path.write_text(
        """
{
  "provider": "test-provider",
  "kind": "audio",
  "cache_ttl_seconds": 120,
  "default_model": "test:v1",
  "languages": ["en-IN"],
  "models": {
    "test:v1": {
      "voices": [
        {
          "id": "sample",
          "name": "Sample Voice",
          "gender": "female",
          "description": "Loaded from JSON"
        }
      ]
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    data = load_catalog(path)

    assert data["provider"] == "test-provider"
    assert data["cache_ttl_seconds"] == 120
    assert data["models"]["test:v1"]["voices"] == [
        {
            "id": "sample",
            "name": "Sample Voice",
            "gender": "female",
            "description": "Loaded from JSON",
        }
    ]
    assert CATALOG_PATH.name == "voices.json"


async def test_router_rejects_invalid_interrupt_turn_id():
    pipeline = _PipelineStub()

    await handle_control_text(pipeline, '{"type":"interrupt","turn_id":""}')
    await handle_control_text(pipeline, '{"type":"interrupt","turn_id":42}')

    assert pipeline.interrupts == []
    assert [event["stage"] for event in pipeline.transport.events] == [
        "protocol",
        "protocol",
    ]


async def test_router_forwards_turn_targeted_interrupt():
    pipeline = _PipelineStub()

    await handle_control_text(
        pipeline,
        '{"type":"interrupt","reason":"barge_in","turn_id":"turn-7"}',
    )

    assert pipeline.interrupts == [("barge_in", "turn-7")]
    assert pipeline.transport.events == []


async def test_voice_catalog_endpoint_is_cacheable():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/voice/voices")

    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("public, max-age=86400")
    payload = response.json()
    assert payload["provider"] == "sarvam"
    assert payload["voices"]


async def test_websocket_accepts_client_signals_before_ready():
    settings = _router_settings(
        require_browser_client=True,
        rate_limit_enabled=False,
    )
    limiter = StrictRateLimiter(settings)
    websocket = _FakeWebSocket(
        app=_router_app(settings, limiter),
        messages=[
            {
                "type": "websocket.receive",
                "text": (
                    '{"type":"configure","client":{'
                    '"installation_id":"12345678-1234-1234-1234-123456789abc",'
                    '"screen_width":1440,"screen_height":900,'
                    '"viewport_width":1280,"viewport_height":800,'
                    '"pixel_ratio":1,"color_depth":24,'
                    '"timezone":"Asia/Kolkata","language":"en-US",'
                    '"platform":"Linux x86_64","hardware_concurrency":8,'
                    '"device_memory":8,"touch_points":0,"webdriver":false}}'
                ),
            },
            {"type": "websocket.disconnect", "code": 1000},
        ],
    )
    websocket.headers["user-agent"] = (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
    )

    await serve_voice_socket(websocket)
    await asyncio.sleep(0.05)

    ready = next(
        (event for event in websocket.sent if event["type"] == "ready"),
        None,
    )
    assert ready is not None, websocket.sent
    assert ready["type"] == "ready"
    assert ready["platform"]["limited"] is True
    assert ready["platform"]["turn_limit"] > 0
