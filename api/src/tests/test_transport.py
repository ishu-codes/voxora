import asyncio
from typing import AsyncIterator

import pytest

from src.voice.runtime.transport import QueueTransport


class BlockingWebSocket:
    """A socket that never finishes sending, to saturate the writer queue."""

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, event: dict) -> None:
        await self.gate.wait()
        self.sent.append(event)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


async def test_audio_events_are_dropped_when_queue_is_full():
    websocket = BlockingWebSocket()
    transport = QueueTransport(websocket, max_queue=2)

    for _ in range(6):
        await transport.send({"type": "audio.chunk", "data": "x"})

    assert transport.dropped >= 3

    # Control events wait briefly, then are counted as dropped instead of
    # blocking the pipeline forever.
    await transport.send({"type": "state", "state": "speaking"})
    assert transport.dropped >= 4

    await asyncio.wait_for(transport.close(), timeout=5)
    assert transport.closed


async def test_writer_sends_events_in_order():
    websocket = BlockingWebSocket()
    websocket.gate.set()
    transport = QueueTransport(websocket, max_queue=8)

    await transport.send({"type": "state", "state": "listening"})
    await transport.send({"type": "assistant.delta", "text": "hi"})
    await transport.close()

    assert [event["type"] for event in websocket.sent] == ["state", "assistant.delta"]
