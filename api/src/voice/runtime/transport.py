"""Transport abstraction so the pipeline can be tested without a socket."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)

_SENTINEL = object()


class Transport(Protocol):
    async def send(self, event: dict[str, Any]) -> None: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class QueueTransport:
    """Bounded writer used by the WebSocket route.

    Slow browsers cannot apply unbounded backpressure to the inference pipeline:
    audio and level events are dropped once the queue is saturated, while
    control events wait briefly and then surface an overload error.
    """

    def __init__(self, websocket: Any, max_queue: int = 256) -> None:
        self._websocket = websocket
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=max_queue)
        self._writer = asyncio.create_task(self._write_loop())
        self.dropped = 0
        self.closed = False

    async def send(self, event: dict[str, Any]) -> None:
        if self.closed:
            return
        event_type = str(event.get("type", ""))
        if event_type == "audio.chunk":
            logger.debug(
                "-> audio.chunk turn=%s encoded_chars=%d",
                event.get("turn_id"),
                len(str(event.get("data", ""))),
            )
        else:
            logger.debug("-> %s", event_type)
        # Timing markers are advisory. Never let a saturated output queue make
        # metrics instrumentation delay the token/audio path.
        droppable = event_type in {"audio.chunk", "audio.level", "turn.timing"}
        if droppable:
            if self._queue.full():
                self.dropped += 1
                logger.warning("Dropping %s: output queue saturated", event_type)
                return
            self._queue.put_nowait(event)
            return
        try:
            await asyncio.wait_for(self._queue.put(event), timeout=1.0)
        except asyncio.TimeoutError:
            self.dropped += 1
            logger.warning("Dropping control event %s: output queue saturated", event_type)

    async def _write_loop(self) -> None:
        while True:
            event = await self._queue.get()
            if event is _SENTINEL:
                return
            try:
                await self._websocket.send_json(event)
            except Exception:
                if not self.closed:
                    logger.debug("WebSocket writer stopped", exc_info=True)
                return

    async def close(self, code: int = 1000, reason: str = "") -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self._queue.put_nowait(_SENTINEL)
        except asyncio.QueueFull:
            pass
        try:
            await asyncio.wait_for(self._writer, timeout=1.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self._writer.cancel()
        try:
            await self._websocket.close(code=code, reason=reason)
        except Exception:
            pass


class CollectingTransport:
    """Test transport that records events in order."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.closed = False

    async def send(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True

    def of_type(self, event_type: str) -> list[dict[str, Any]]:
        return [event for event in self.events if event.get("type") == event_type]


__all__ = ["Transport", "QueueTransport", "CollectingTransport"]
