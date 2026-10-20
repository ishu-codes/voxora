from src.voice.config import Settings
from src.voice.rate_limit import (
    ClientSignals,
    StrictRateLimiter,
    browser_client_issue,
    build_device_identity,
    client_ip,
)


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


async def test_byok_turns_bypass_provider_turn_quota():
    settings = Settings(
        rate_limit_secret="test-secret",
        rate_limit_platform_turns_hour=1,
    )
    limiter = StrictRateLimiter(settings)
    identity = _identity(limiter)

    assert (await limiter.allow_turn(identity, byok=True)).allowed
    assert (await limiter.allow_turn(identity, byok=True)).allowed


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

    assert client_ip(
        "10.0.0.1", headers, trust_proxy_headers=False
    ) == "10.0.0.1"
    assert client_ip(
        "10.0.0.1", headers, trust_proxy_headers=True
    ) == "198.51.100.7"


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

    assert browser_client_issue(
        origin="https://voxora.test",
        user_agent=browser_ua,
        signals=complete,
    ) is None
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
