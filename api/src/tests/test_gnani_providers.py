import asyncio
import base64
import json

import pytest

from src.voice.core.config import Settings
from src.voice.providers.base import ProviderError
from src.voice.providers.gnani_stt import GnaniSTT
from src.voice.providers.gnani_tts import GnaniTTS


class FakeGnaniSTTSocket:
    close_code = None

    def __init__(self) -> None:
        self.sent: list[bytes | str] = []
        self._events: asyncio.Queue[str | None] = asyncio.Queue()
        self._audio = bytearray()

    async def send(self, frame: bytes | str) -> None:
        self.sent.append(frame)
        if isinstance(frame, bytes):
            self._audio.extend(frame)
            return
        message = json.loads(frame)
        if message.get("type") == "commit":
            self._events.put_nowait(
                json.dumps(
                    {
                        "type": "transcript",
                        "text": "aata do kilo",
                        "segment_index": 1,
                        "audio_duration_ms": 480,
                    }
                )
            )

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        item = await self._events.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def close(self) -> None:
        self._events.put_nowait(None)


class FakeGnaniTTSSocket:
    close_code = None

    def __init__(self, error: str | None = None) -> None:
        self.sent: list[dict] = []
        self._events: asyncio.Queue[str] = asyncio.Queue()
        self._error = error

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))
        if self._error:
            self._events.put_nowait(
                json.dumps({"type": "error", "message": self._error})
            )
            return
        self._events.put_nowait(
            json.dumps(
                {
                    "type": "audio",
                    "data": {
                        "audio": base64.b64encode(b"\x00\x01" * 64).decode()
                    },
                }
            )
        )
        self._events.put_nowait(
            json.dumps({"type": "complete", "data": {"is_final": True}})
        )

    async def recv(self) -> str:
        return await self._events.get()

    async def close(self) -> None:
        self.close_code = 1000


class DelayedFakeGnaniTTSSocket(FakeGnaniTTSSocket):
    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

        async def respond() -> None:
            await asyncio.sleep(0.05)
            self._events.put_nowait(
                json.dumps(
                    {
                        "type": "audio",
                        "data": {
                            "audio": base64.b64encode(b"\x00\x01" * 64).decode()
                        },
                    }
                )
            )
            self._events.put_nowait(
                json.dumps({"type": "complete", "data": {"is_final": True}})
            )

        asyncio.create_task(respond())


async def _collect_chunks(iterator) -> list[bytes]:
    return [chunk async for chunk in iterator]


async def test_gnani_stt_rebuffers_1024_byte_frames_and_parses_transcript(
    monkeypatch,
):
    socket = FakeGnaniSTTSocket()

    async def connect(*_args, **_kwargs):
        return socket

    monkeypatch.setattr("websockets.connect", connect)
    stt = GnaniSTT(
        Settings(
            stt_provider="gnani",
            gnani_api_key="test-key",
            gnani_stt_language="hi-IN",
        )
    )

    await stt.begin_utterance()
    await stt.push_audio(b"\x00\x01" * 800)
    text = await stt.end_utterance()

    assert text == "aata do kilo"
    audio_frames = [item for item in socket.sent if isinstance(item, bytes)]
    assert len(audio_frames) == 2
    assert all(len(frame) == 1_024 for frame in audio_frames)
    assert json.loads(socket.sent[-1]) == {"type": "commit"}
    await stt.close()


async def test_gnani_stt_surfaces_stream_error(monkeypatch):
    class BrokenSocket(FakeGnaniSTTSocket):
        async def send(self, frame: bytes | str) -> None:
            if isinstance(frame, str) and json.loads(frame).get("type") == "commit":
                self._events.put_nowait(
                    json.dumps({"type": "error", "message": "engine unavailable"})
                )
                return
            await super().send(frame)

    socket = BrokenSocket()

    async def connect(*_args, **_kwargs):
        return socket

    monkeypatch.setattr("websockets.connect", connect)
    stt = GnaniSTT(
        Settings(
            stt_provider="gnani",
            gnani_api_key="test-key",
            provider_retry_attempts=1,
        )
    )
    await stt.begin_utterance()
    with pytest.raises(ProviderError, match="engine unavailable"):
        await stt.end_utterance()
    await stt.close()


async def test_gnani_tts_requests_raw_pcm_and_parses_audio(monkeypatch):
    socket = FakeGnaniTTSSocket()

    async def connect(*_args, **_kwargs):
        return socket

    monkeypatch.setattr("websockets.connect", connect)
    tts = GnaniTTS(
        Settings(
            tts_provider="gnani",
            gnani_api_key="test-key",
            tts_sample_rate=22_050,
        )
    )

    chunks = [chunk async for chunk in tts.synthesize("Namaste.", "Poorvi")]

    assert chunks == [b"\x00\x01" * 64]
    request = socket.sent[0]
    assert request["model"] == "timbre-v2.5"
    assert request["language"] == "hi-en"
    assert request["audio_config"] == {
        "sample_rate": 22_050,
        "num_channels": 1,
        "sample_width": 2,
        "encoding": "pcm_s16le",
        "container": "raw",
    }
    await tts.close()


async def test_gnani_tts_surfaces_documented_error(monkeypatch):
    socket = FakeGnaniTTSSocket("invalid voice")

    async def connect(*_args, **_kwargs):
        return socket

    monkeypatch.setattr("websockets.connect", connect)
    tts = GnaniTTS(
        Settings(
            tts_provider="gnani",
            gnani_api_key="test-key",
            provider_retry_attempts=1,
        )
    )

    with pytest.raises(ProviderError, match="invalid voice"):
        async for _chunk in tts.synthesize("Hello.", "NotAVoice"):
            pass
    await tts.close()


async def test_gnani_tts_prewarm_does_not_close_active_synthesis(monkeypatch):
    socket = DelayedFakeGnaniTTSSocket()

    async def connect(*_args, **_kwargs):
        return socket

    monkeypatch.setattr("websockets.connect", connect)
    tts = GnaniTTS(
        Settings(
            tts_provider="gnani",
            gnani_api_key="test-key",
            provider_retry_attempts=1,
        )
    )

    synthesis = asyncio.create_task(
        _collect_chunks(tts.synthesize("Hello.", "Kaveri"))
    )
    await asyncio.sleep(0.01)
    prewarm = asyncio.create_task(tts.prepare("Kaveri"))
    chunks = await synthesis
    await prewarm

    assert chunks == [b"\x00\x01" * 64]
    await tts.close()


async def test_gnani_tts_uses_a_fresh_socket_for_each_synthesis(monkeypatch):
    sockets: list[FakeGnaniTTSSocket] = []

    async def connect(*_args, **_kwargs):
        socket = FakeGnaniTTSSocket()
        sockets.append(socket)
        return socket

    monkeypatch.setattr("websockets.connect", connect)
    tts = GnaniTTS(
        Settings(
            tts_provider="gnani",
            gnani_api_key="test-key",
            provider_retry_attempts=1,
        )
    )

    first = await _collect_chunks(tts.synthesize("First.", "Kaveri"))
    second = await _collect_chunks(tts.synthesize("Second.", "Kaveri"))

    assert first and second
    assert len(sockets) == 2
    assert sockets[0].close_code == 1000
    await tts.close()


async def test_gnani_adapters_require_server_side_keys():
    stt = GnaniSTT(Settings(gnani_api_key=""))
    tts = GnaniTTS(Settings(gnani_api_key=""))

    with pytest.raises(ProviderError, match="API key"):
        await stt.begin_utterance()
    with pytest.raises(ProviderError, match="API key"):
        async for _chunk in tts.synthesize("Hello."):
            pass
