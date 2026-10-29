import json
from types import SimpleNamespace

import pytest

from src.voice.core.config import Settings
from src.voice.providers.llm import EchoLLM
from src.voice.security.rate_limit import (
    ClientSignals,
    StrictRateLimiter,
    browser_client_issue,
    build_device_identity,
    client_ip,
)
from src.voice.services.provider_bundle import ProviderBundle
from src.voice.services.voice import read_initial_config, serve_voice_socket


def _identity(limiter: StrictRateLimiter, *, ip: str = "203.0.113.8"):
    return limiter.identity(
        ip=ip,
        user_agent="Browser/1.0",
        origin="https://voxora.test",
        signals=ClientSignals(
            installation_id="device-1",
            screen_width=1440,
            screen_height=900,
            timezone="Asia/Kolkata",
            platform="MacIntel",
        ),
    )


class _FakeWebSocket:
    def __init__(
        self,
        *,
        app,
        messages: list[dict] | None = None,
    ) -> None:
        self.app = app
        self.headers = {
            "origin": "https://voxora.test",
            "user-agent": "Browser/1.0",
        }
        self.client = SimpleNamespace(host="203.0.113.8", port=4321)
        self.messages = list(messages or [])
        self.sent: list[dict] = []
        self.accepted = False
        self.closed: tuple[int, str] | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def receive(self) -> dict:
        if not self.messages:
            pytest.fail("router attempted to read after a pre-provider rejection")
        return self.messages.pop(0)

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = (code, reason)


def _router_settings(**overrides) -> Settings:
    values = {
        "cors_origins": ("https://voxora.test",),
        "rate_limit_secret": "test-secret",
        "require_browser_client": False,
        "sarvam_api_key": "",
        "llm_api_key": "",
    }
    values.update(overrides)
    return Settings(**values)


def _router_app(settings: Settings, limiter: StrictRateLimiter):
    return SimpleNamespace(
        state=SimpleNamespace(
            voice_providers=ProviderBundle(
                settings=settings,
                llm=EchoLLM(),
            ),
            rate_limiter=limiter,
        )
    )


async def test_identity_allows_one_concurrent_session():
    settings = Settings(
        rate_limit_secret="test-secret",
        rate_limit_identity_sessions_hour=5,
        rate_limit_max_concurrent_identity=1,
    )
    limiter = StrictRateLimiter(settings)
    identity = _identity(limiter)

    assert (await limiter.acquire(identity)).allowed
    denied = await limiter.acquire(identity)
    assert not denied.allowed
    assert "already active" in denied.message

    await limiter.release(identity)
    assert (await limiter.acquire(identity)).allowed
    await limiter.release(identity)


async def test_cross_session_turn_quota_is_enforced():
    settings = Settings(
        rate_limit_secret="test-secret",
        rate_limit_platform_turns_hour=2,
        rate_limit_platform_turns_day=10,
    )
    limiter = StrictRateLimiter(settings)
    identity = _identity(limiter)

    assert (await limiter.allow_turn(identity)).allowed
    assert (await limiter.allow_turn(identity)).allowed
    denied = await limiter.allow_turn(identity)
    assert not denied.allowed
    assert denied.retry_after_s > 0


async def test_turn_quota_has_no_bypass():
    settings = Settings(
        rate_limit_secret="test-secret",
        rate_limit_platform_turns_hour=1,
    )
    limiter = StrictRateLimiter(settings)
    identity = _identity(limiter)

    assert (await limiter.allow_turn(identity)).allowed
    assert not (await limiter.allow_turn(identity)).allowed


async def test_stt_llm_and_tts_usage_are_budgeted_separately():
    settings = Settings(
        rate_limit_secret="test-secret",
        rate_limit_stt_chars_hour=10,
        rate_limit_stt_chars_day=100,
        rate_limit_llm_chars_hour=20,
        rate_limit_llm_chars_day=100,
        rate_limit_llm_tokens_hour=5,
        rate_limit_llm_tokens_day=100,
        rate_limit_tts_chars_hour=30,
        rate_limit_tts_chars_day=100,
    )
    limiter = StrictRateLimiter(settings)
    identity = _identity(limiter)

    assert (await limiter.consume_usage(identity, kind="stt", chars=9)).allowed
    assert not (await limiter.consume_usage(identity, kind="stt", chars=2)).allowed
    assert (
        await limiter.consume_usage(identity, kind="llm", chars=10, tokens=4)
    ).allowed
    assert not (
        await limiter.consume_usage(identity, kind="llm", chars=1, tokens=2)
    ).allowed
    assert (await limiter.consume_usage(identity, kind="tts", chars=30)).allowed
    assert not (await limiter.consume_usage(identity, kind="tts", chars=1)).allowed


async def test_ip_attempt_window_expires():
    now = 1_000.0
    settings = Settings(
        rate_limit_secret="test-secret",
        rate_limit_ip_attempts_10m=2,
        rate_limit_ip_attempts_day=10,
    )
    limiter = StrictRateLimiter(settings, clock=lambda: now)
    identity = _identity(limiter)

    assert (await limiter.record_ip_attempt(identity.ip_key)).allowed
    assert (await limiter.record_ip_attempt(identity.ip_key)).allowed
    assert not (await limiter.record_ip_attempt(identity.ip_key)).allowed

    now += 601
    assert (await limiter.record_ip_attempt(identity.ip_key)).allowed


async def test_router_rejects_ip_limit_before_provider_setup(monkeypatch):
    settings = _router_settings(
        rate_limit_ip_attempts_10m=2,
        rate_limit_ip_attempts_day=10,
    )
    limiter = StrictRateLimiter(settings)
    ip_key = limiter.identity(
        ip="203.0.113.8",
        user_agent="Browser/1.0",
        origin="https://voxora.test",
        signals=ClientSignals(),
    ).ip_key
    assert (await limiter.record_ip_attempt(ip_key)).allowed
    assert (await limiter.record_ip_attempt(ip_key)).allowed
    websocket = _FakeWebSocket(app=_router_app(settings, limiter))

    def fail_provider_setup(*_args, **_kwargs):
        pytest.fail("provider setup must not run for an IP-rate-limited request")

    monkeypatch.setattr(ProviderBundle, "build", fail_provider_setup)
    await serve_voice_socket(websocket)

    assert websocket.accepted
    assert websocket.sent[-1]["stage"] == "rate_limit"
    assert websocket.closed == (1008, "Rate limit exceeded")


async def test_configure_frame_does_not_accept_provider_keys():
    websocket = _FakeWebSocket(
        app=SimpleNamespace(state=SimpleNamespace()),
        messages=[
            {
                "type": "websocket.receive",
                "text": json.dumps(
                    {
                        "type": "configure",
                        "byok": {
                            "sarvam_api_key": "ignored",
                            "openai_api_key": "ignored",
                        },
                        "client": {
                            "installation_id": "device-1",
                            "timezone": "Asia/Kolkata",
                        },
                    }
                ),
            }
        ],
    )

    client_payload, audio, disconnected = await read_initial_config(websocket)

    assert disconnected is False
    assert audio == []
    assert client_payload["installation_id"] == "device-1"
    assert websocket.sent[-1]["stage"] == "config"
    assert "not accepted" in websocket.sent[-1]["message"]
    assert "ignored" not in json.dumps(client_payload)


async def test_router_rejects_duplicate_identity_before_provider_setup(monkeypatch):
    settings = _router_settings(
        rate_limit_identity_sessions_hour=5,
        rate_limit_max_concurrent_identity=1,
    )
    limiter = StrictRateLimiter(settings)
    signals = ClientSignals(
        installation_id="device-1",
        screen_width=1440,
        screen_height=900,
        timezone="Asia/Kolkata",
        language="en-IN",
        platform="Linux",
    )
    active_identity = limiter.identity(
        ip="203.0.113.8",
        user_agent="Browser/1.0",
        origin="https://voxora.test",
        signals=signals,
    )
    assert (await limiter.acquire(active_identity)).allowed
    websocket = _FakeWebSocket(
        app=_router_app(settings, limiter),
        messages=[
            {
                "type": "websocket.receive",
                "text": json.dumps(
                    {
                        "type": "configure",
                        "byok": {},
                        "client": {
                            "installation_id": "device-1",
                            "screen_width": 1440,
                            "screen_height": 900,
                            "viewport_width": 1280,
                            "viewport_height": 800,
                            "timezone": "Asia/Kolkata",
                            "language": "en-IN",
                            "platform": "Linux",
                        },
                    }
                ),
            }
        ],
    )

    def fail_provider_setup(*_args, **_kwargs):
        pytest.fail("provider setup must not run for a duplicate session")

    monkeypatch.setattr(ProviderBundle, "build", fail_provider_setup)
    try:
        await serve_voice_socket(websocket)
    finally:
        await limiter.release(active_identity)

    assert websocket.sent[-1]["stage"] == "rate_limit"
    assert websocket.closed == (1008, "Rate limit exceeded")


def test_fingerprint_is_hmac_and_changes_with_ip_or_device():
    kwargs = {
        "user_agent": "Browser/1.0",
        "origin": "https://voxora.test",
        "signals": ClientSignals(installation_id="device-1", screen_width=1440),
        "secret": b"test-secret",
    }
    first = build_device_identity(ip="203.0.113.8", **kwargs)
    same = build_device_identity(ip="203.0.113.8", **kwargs)
    other_ip = build_device_identity(ip="203.0.113.9", **kwargs)

    assert first.identity_key == same.identity_key
    assert first.identity_key != other_ip.identity_key
    assert first.identity_key != "203.0.113.8"
    assert len(first.identity_key) == 64


def test_screen_orientation_does_not_change_identity():
    kwargs = {
        "ip": "203.0.113.8",
        "user_agent": "Browser/1.0",
        "origin": "https://voxora.test",
        "secret": b"test-secret",
    }
    portrait = build_device_identity(
        **kwargs,
        signals=ClientSignals(
            installation_id="device-1",
            screen_width=390,
            screen_height=844,
            viewport_width=390,
            viewport_height=700,
        ),
    )
    landscape = build_device_identity(
        **kwargs,
        signals=ClientSignals(
            installation_id="device-1",
            screen_width=844,
            screen_height=390,
            viewport_width=800,
            viewport_height=600,
        ),
    )

    assert portrait.identity_key == landscape.identity_key


def test_forwarded_ip_is_only_used_when_proxy_headers_are_trusted():
    headers = {"x-forwarded-for": "198.51.100.7, 10.0.0.2"}

    assert client_ip("10.0.0.1", headers, trust_proxy_headers=False) == "10.0.0.1"
    assert client_ip("10.0.0.1", headers, trust_proxy_headers=True) == "198.51.100.7"


def test_browser_gate_rejects_curl_and_incomplete_browser_signals():
    browser_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
    )
    complete = ClientSignals(
        installation_id="12345678-1234-1234-1234-123456789abc",
        screen_width=1440,
        screen_height=900,
        viewport_width=1280,
        viewport_height=800,
        timezone="Asia/Kolkata",
        language="en-IN",
        platform="Win32",
    )

    assert (
        browser_client_issue(
            origin="https://voxora.test",
            user_agent=browser_ua,
            signals=complete,
        )
        is None
    )
    assert browser_client_issue(
        origin=None,
        user_agent=browser_ua,
        signals=complete,
    )
    assert browser_client_issue(
        origin="https://voxora.test",
        user_agent="curl/8.10.0",
        signals=complete,
    )
    assert browser_client_issue(
        origin="https://voxora.test",
        user_agent=browser_ua,
        signals=ClientSignals(),
    )
