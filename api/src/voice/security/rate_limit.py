"""Cross-session abuse controls for the anonymous voice product.

The limiter keys buckets with an HMAC of coarse device signals, the client IP
and the server-derived user agent. Raw signals are never logged or retained.
This implementation is process-local; deployments with multiple workers should
replace the event store with Redis or another shared atomic counter.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import math
import re
import secrets
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field

from ..core.config import Settings

logger = logging.getLogger(__name__)

WINDOW_10M = 10 * 60
WINDOW_HOUR = 60 * 60
WINDOW_DAY = 24 * 60 * 60
_BROWSER_UA = re.compile(
    r"Mozilla/5\.0.*(?:Chrome/|Firefox/|Safari/|Edg/|OPR/)",
    re.IGNORECASE,
)
_NON_BROWSER_UA = {
    "curl",
    "wget",
    "python-requests",
    "python-urllib",
    "httpx",
    "postmanruntime",
    "go-http-client",
    "node-fetch",
    "undici",
    "headlesschrome",
}


@dataclass(frozen=True, slots=True)
class ClientSignals:
    installation_id: str = ""
    screen_width: int = 0
    screen_height: int = 0
    viewport_width: int = 0
    viewport_height: int = 0
    pixel_ratio: float = 0.0
    color_depth: int = 0
    timezone: str = ""
    language: str = ""
    platform: str = ""
    hardware_concurrency: int = 0
    device_memory: float = 0.0
    touch_points: int = 0
    webdriver: bool = False

    @classmethod
    def from_payload(cls, value: object) -> ClientSignals:
        if not isinstance(value, dict):
            return cls()

        def integer(key: str, maximum: int) -> int:
            item = value.get(key)
            if not isinstance(item, (int, float)) or isinstance(item, bool):
                return 0
            return max(0, min(maximum, int(item)))

        def number(key: str, maximum: float) -> float:
            item = value.get(key)
            if not isinstance(item, (int, float)) or isinstance(item, bool):
                return 0.0
            if not math.isfinite(item):
                return 0.0
            return max(0.0, min(maximum, float(item)))

        def text(key: str, limit: int) -> str:
            item = value.get(key)
            if not isinstance(item, str):
                return ""
            return " ".join(item.split())[:limit]

        return cls(
            installation_id=text("installation_id", 128),
            screen_width=integer("screen_width", 32_768),
            screen_height=integer("screen_height", 32_768),
            viewport_width=integer("viewport_width", 32_768),
            viewport_height=integer("viewport_height", 32_768),
            pixel_ratio=number("pixel_ratio", 16),
            color_depth=integer("color_depth", 128),
            timezone=text("timezone", 128),
            language=text("language", 128),
            platform=text("platform", 128),
            hardware_concurrency=integer("hardware_concurrency", 1_024),
            device_memory=number("device_memory", 4_096),
            touch_points=integer("touch_points", 64),
            webdriver=value.get("webdriver") is True,
        )


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    """Hashed identifiers used only as limiter bucket keys."""

    identity_key: str
    ip_key: str


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    message: str = ""
    retry_after_s: int = 0

    @classmethod
    def accept(cls) -> RateLimitDecision:
        return cls(True)

    @classmethod
    def deny(cls, message: str, retry_after_s: int) -> RateLimitDecision:
        return cls(False, message, max(1, retry_after_s))


def client_ip(
    client_host: str | None,
    headers: Mapping[str, str],
    *,
    trust_proxy_headers: bool,
) -> str:
    """Resolve the caller IP without blindly trusting arbitrary proxy headers."""
    if trust_proxy_headers:
        forwarded = headers.get("x-forwarded-for", "")
        if forwarded:
            candidate = forwarded.split(",", 1)[0].strip()
            if candidate:
                return candidate
        real_ip = headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
    return (client_host or "unknown").strip()[:128]


def browser_client_issue(
    *,
    origin: str | None,
    user_agent: str,
    signals: ClientSignals,
) -> str | None:
    """Return a reason when the handshake is not from an interactive browser."""
    transport_issue = browser_transport_issue(origin, user_agent)
    if transport_issue:
        return transport_issue
    if signals.webdriver:
        return "Automated browser sessions are not supported."
    if len(signals.installation_id) < 16:
        return "The browser device identifier is missing."
    if (
        signals.screen_width <= 0
        or signals.screen_height <= 0
        or signals.viewport_width <= 0
        or signals.viewport_height <= 0
    ):
        return "The browser viewport information is incomplete."
    if not signals.timezone or not signals.language or not signals.platform:
        return "The browser environment information is incomplete."
    return None


def browser_transport_issue(origin: str | None, user_agent: str) -> str | None:
    lowered = user_agent.lower()
    if not origin:
        return "A browser Origin header is required."
    if any(marker in lowered for marker in _NON_BROWSER_UA) or not _BROWSER_UA.search(
        user_agent
    ):
        return "Automated and command-line clients are not supported."
    return None


def build_device_identity(
    *,
    ip: str,
    user_agent: str,
    origin: str,
    signals: ClientSignals,
    secret: bytes,
) -> DeviceIdentity:
    signals_data = asdict(signals)
    # Window resizing and orientation changes must not create a fresh identity.
    signals_data.pop("viewport_width", None)
    signals_data.pop("viewport_height", None)
    screen_width = signals_data["screen_width"]
    screen_height = signals_data["screen_height"]
    signals_data["screen_width"] = min(screen_width, screen_height)
    signals_data["screen_height"] = max(screen_width, screen_height)
    payload = {
        "ip": ip,
        "user_agent": user_agent,
        "origin": origin,
        "signals": signals_data,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    identity_key = hmac.new(secret, canonical.encode(), hashlib.sha256).hexdigest()
    ip_key = hmac.new(secret, f"ip:{ip}".encode(), hashlib.sha256).hexdigest()
    return DeviceIdentity(identity_key=identity_key, ip_key=ip_key)


@dataclass(slots=True)
class _Bucket:
    events: deque[float] = field(default_factory=deque)


class StrictRateLimiter:
    """Sliding-window limits shared across sessions in this API process."""

    def __init__(
        self,
        settings: Settings,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self._clock = clock
        self._secret = (
            settings.rate_limit_secret.encode()
            if settings.rate_limit_secret
            else secrets.token_bytes(32)
        )
        if settings.rate_limit_enabled and not settings.rate_limit_secret:
            logger.warning(
                "RATE_LIMIT_SECRET is unset; fingerprints are limited to this process"
            )
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._usage_buckets: dict[tuple[str, str], deque[tuple[float, float]]] = {}
        self._active: dict[str, int] = {}
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self.settings.rate_limit_enabled

    def identity(
        self,
        *,
        ip: str,
        user_agent: str,
        origin: str,
        signals: ClientSignals,
    ) -> DeviceIdentity:
        return build_device_identity(
            ip=ip,
            user_agent=user_agent,
            origin=origin,
            signals=signals,
            secret=self._secret,
        )

    async def record_ip_attempt(self, ip_key: str) -> RateLimitDecision:
        if not self.enabled:
            return RateLimitDecision.accept()
        async with self._lock:
            now = self._clock()
            denied = self._check_windows(
                now,
                (
                    (
                        "ip_attempt_10m",
                        ip_key,
                        self.settings.rate_limit_ip_attempts_10m,
                        WINDOW_10M,
                    ),
                    (
                        "ip_attempt_day",
                        ip_key,
                        self.settings.rate_limit_ip_attempts_day,
                        WINDOW_DAY,
                    ),
                ),
            )
            if denied is not None:
                return denied
            self._record("ip_attempt_10m", ip_key, now)
            self._record("ip_attempt_day", ip_key, now)
            return RateLimitDecision.accept()

    async def acquire(self, identity: DeviceIdentity) -> RateLimitDecision:
        if not self.enabled:
            return RateLimitDecision.accept()
        key = identity.identity_key
        async with self._lock:
            now = self._clock()
            if (
                self._active.get(key, 0)
                >= self.settings.rate_limit_max_concurrent_identity
            ):
                return RateLimitDecision.deny(
                    "Another voice session is already active for this device.",
                    10,
                )
            denied = self._check_windows(
                now,
                (
                    (
                        "identity_attempt_10m",
                        key,
                        self.settings.rate_limit_identity_attempts_10m,
                        WINDOW_10M,
                    ),
                    (
                        "identity_session_hour",
                        key,
                        self.settings.rate_limit_identity_sessions_hour,
                        WINDOW_HOUR,
                    ),
                    (
                        "identity_session_day",
                        key,
                        self.settings.rate_limit_identity_sessions_day,
                        WINDOW_DAY,
                    ),
                ),
            )
            if denied is not None:
                return denied
            self._record("identity_attempt_10m", key, now)
            self._record("identity_session_hour", key, now)
            self._record("identity_session_day", key, now)
            self._active[key] = self._active.get(key, 0) + 1
            return RateLimitDecision.accept()

    async def release(self, identity: DeviceIdentity) -> None:
        if not self.enabled:
            return
        async with self._lock:
            key = identity.identity_key
            active = self._active.get(key, 0) - 1
            if active > 0:
                self._active[key] = active
            else:
                self._active.pop(key, None)

    async def allow_turn(
        self,
        identity: DeviceIdentity,
    ) -> RateLimitDecision:
        if not self.enabled:
            return RateLimitDecision.accept()
        key = identity.identity_key
        async with self._lock:
            now = self._clock()
            denied = self._check_windows(
                now,
                (
                    (
                        "platform_turn_hour",
                        key,
                        self.settings.rate_limit_platform_turns_hour,
                        WINDOW_HOUR,
                    ),
                    (
                        "platform_turn_day",
                        key,
                        self.settings.rate_limit_platform_turns_day,
                        WINDOW_DAY,
                    ),
                ),
            )
            if denied is not None:
                return denied
            self._record("platform_turn_hour", key, now)
            self._record("platform_turn_day", key, now)
            return RateLimitDecision.accept()

    async def consume_usage(
        self,
        identity: DeviceIdentity,
        *,
        kind: str,
        chars: int = 0,
        tokens: int = 0,
    ) -> RateLimitDecision:
        if not self.enabled:
            return RateLimitDecision.accept()
        if chars <= 0 and tokens <= 0:
            return RateLimitDecision.accept()
        if kind not in {"stt", "llm", "tts"}:
            raise ValueError(f"Unknown usage kind: {kind}")
        key = identity.identity_key
        char_limit_hour = getattr(self.settings, f"rate_limit_{kind}_chars_hour")
        char_limit_day = getattr(self.settings, f"rate_limit_{kind}_chars_day")
        windows: list[tuple[str, str, int, int, float]] = []
        if chars > 0:
            windows.extend(
                (
                    (f"{kind}_chars_hour", key, char_limit_hour, WINDOW_HOUR, chars),
                    (f"{kind}_chars_day", key, char_limit_day, WINDOW_DAY, chars),
                )
            )
        if kind == "llm" and tokens > 0:
            windows.extend(
                (
                    (
                        "llm_tokens_hour",
                        key,
                        self.settings.rate_limit_llm_tokens_hour,
                        WINDOW_HOUR,
                        tokens,
                    ),
                    (
                        "llm_tokens_day",
                        key,
                        self.settings.rate_limit_llm_tokens_day,
                        WINDOW_DAY,
                        tokens,
                    ),
                )
            )

        async with self._lock:
            now = self._clock()
            for scope, bucket_key, limit, width, amount in windows:
                bucket = self._usage_buckets.setdefault((scope, bucket_key), deque())
                cutoff = now - width
                while bucket and bucket[0][0] <= cutoff:
                    bucket.popleft()
                used = sum(event_amount for _, event_amount in bucket)
                if limit <= 0 or used + amount > limit:
                    retry_after = (
                        math.ceil(bucket[0][0] + width - now)
                        if bucket
                        else max(1, width)
                    )
                    label = {
                        "stt": "speech recognition",
                        "llm": "response generation",
                        "tts": "speech synthesis",
                    }[kind]
                    return RateLimitDecision.deny(
                        f"{label.title()} usage limit reached for this device.",
                        retry_after,
                    )
            for scope, bucket_key, _limit, _width, amount in windows:
                self._usage_buckets.setdefault((scope, bucket_key), deque()).append(
                    (now, amount)
                )
            return RateLimitDecision.accept()

    def _record(self, scope: str, key: str, now: float) -> None:
        self._buckets.setdefault((scope, key), _Bucket()).events.append(now)

    def _check_windows(
        self,
        now: float,
        windows: tuple[tuple[str, str, int, int], ...],
    ) -> RateLimitDecision | None:
        for scope, key, limit, width in windows:
            bucket = self._buckets.setdefault((scope, key), _Bucket())
            cutoff = now - width
            while bucket.events and bucket.events[0] <= cutoff:
                bucket.events.popleft()
            if limit <= 0 or len(bucket.events) >= limit:
                retry_after = (
                    math.ceil(bucket.events[0] + width - now)
                    if bucket.events
                    else max(1, width)
                )
                return RateLimitDecision.deny(
                    "Voice usage limit reached for this device. Try again later.",
                    retry_after,
                )
        return None


__all__ = [
    "ClientSignals",
    "DeviceIdentity",
    "RateLimitDecision",
    "StrictRateLimiter",
    "browser_client_issue",
    "browser_transport_issue",
    "build_device_identity",
    "client_ip",
]
