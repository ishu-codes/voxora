import asyncio
import base64
import json

import pytest

from src.voice.config import Settings
from src.voice.providers import SarvamSTT, SarvamTTS, build_llm
from src.voice.providers.base import ProviderError
from src.voice.providers.llm import EchoLLM, OpenAICompatibleLLM


def test_auto_falls_back_to_demo_llm_without_a_key(monkeypatch):
    for name in ("LLM_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert isinstance(build_llm(Settings())[0], EchoLLM)


def test_explicit_openai_compatible_llm_builds_without_network():
    settings = Settings(llm_provider="openai", llm_api_key="test-key")
    llm, _ = build_llm(settings)
    assert isinstance(llm, OpenAICompatibleLLM)


def test_ollama_preset_uses_local_base_url():
    settings = Settings(
        llm_provider="ollama",
        llm_base_url="http://localhost:11434/v1",
        llm_model="llama3.2",
    )
    assert isinstance(build_llm(settings)[0], OpenAICompatibleLLM)


def test_sarvam_adapters_expose_streaming_metadata():
    settings = Settings(tts_sample_rate=24_000)
    stt = SarvamSTT(settings)
    tts = SarvamTTS(settings)

    assert stt.name == "sarvam"
    assert stt.supports_partials is True
    assert tts.name == "sarvam"
    assert tts.kind == "audio"
    assert tts.sample_rate == 24_000


class FakeSTTSocket:
    """Minimal Sarvam STT server: finalises each utterance on speech_end."""

    def __init__(self) -> None:
        self.close_code = None
        self.sent: list[dict] = []
        self._server: asyncio.Queue[str | None] = asyncio.Queue()
        self._utterances = -1

    async def send(self, raw: str) -> None:
        message = json.loads(raw)
        self.sent.append(message)
        if message.get("event") == "speech_start":
            self._utterances += 1
        elif message.get("event") == "audio_input":
            self._server.put_nowait(
                json.dumps(
                    {
                        "event": "transcript.partial",
                        "utterance_idx": self._utterances,
                        "text": "hel",
                    }
                )
            )
        elif message.get("event") == "speech_end":
            self._server.put_nowait(
                json.dumps(
                    {
                        "event": "transcript.final",
                        "utterance_idx": self._utterances,
                        "text": "hello world",
                    }
                )
            )

    async def recv(self) -> str:
        item = await self._server.get()
        assert item is not None
        return item

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        item = await self._server.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def close(self) -> None:
        self.close_code = 1000
        self._server.put_nowait(None)


class FakeTTSSocket:
    """Minimal Sarvam TTS server: one audio chunk then a completion event."""

    def __init__(self) -> None:
        self.close_code = None
        self.sent: list[dict] = []
        self._server: asyncio.Queue[str] = asyncio.Queue()

    async def send(self, raw: str) -> None:
        message = json.loads(raw)
        self.sent.append(message)
        if message.get("type") == "text":
            self._server.put_nowait(
                json.dumps(
                    {
                        "type": "audio",
                        "data": {
                            "content_type": "audio/pcm",
                            "audio": base64.b64encode(b"\x00\x01" * 64).decode(),
                        },
                    }
                )
            )
        elif message.get("type") == "flush":
            self._server.put_nowait(
                json.dumps({"type": "event", "data": {"event_type": "final"}})
            )

    async def recv(self) -> str:
        return await self._server.get()

    async def close(self) -> None:
        self.close_code = 1000


async def test_sarvam_stt_streams_audio_partials_and_final(monkeypatch):
    socket = FakeSTTSocket()

    async def connect(*_args, **_kwargs):
        return socket

    monkeypatch.setattr("websockets.connect", connect)
    stt = SarvamSTT(Settings(sarvam_api_key="test-key"))
    partials: list[str] = []

    await stt.begin_utterance(lambda text: _collect(partials, text))
    await stt.push_audio(b"\x00\x00" * 160)
    text = await stt.end_utterance()

    assert partials == ["hel"]
    assert text == "hello world"
    events = [message["event"] for message in socket.sent]
    assert events == ["speech_start", "audio_input", "speech_end"]
    assert base64.b64decode(socket.sent[1]["audio"]) == b"\x00\x00" * 160
    await stt.close()


async def _collect(target: list[str], text: str) -> None:
    target.append(text)


async def test_sarvam_tts_configures_and_streams_pcm(monkeypatch):
    socket = FakeTTSSocket()

    async def connect(*_args, **_kwargs):
        return socket

    monkeypatch.setattr("websockets.connect", connect)
    tts = SarvamTTS(Settings(sarvam_api_key="test-key", tts_sample_rate=16_000))

    chunks = [chunk async for chunk in tts.synthesize("Hello there.", voice="ritu")]

    assert chunks == [b"\x00\x01" * 64]
    assert socket.sent[0]["type"] == "config"
    assert socket.sent[0]["data"]["speaker"] == "ritu"
    assert socket.sent[0]["data"]["output_audio_codec"] == "linear16"
    assert socket.sent[0]["data"]["speech_sample_rate"] == "16000"
    assert [message["type"] for message in socket.sent[1:]] == ["text", "flush"]
    await tts.close()


async def test_sarvam_tts_prewarms_connection_without_sending_text(monkeypatch):
    socket = FakeTTSSocket()

    async def connect(*_args, **_kwargs):
        return socket

    monkeypatch.setattr("websockets.connect", connect)
    tts = SarvamTTS(Settings(sarvam_api_key="test-key"))

    await tts.prepare(voice="ritu")

    assert [message["type"] for message in socket.sent] == ["config"]
    assert socket.sent[0]["data"]["speaker"] == "ritu"
    await tts.close()


async def test_sarvam_stt_requires_a_key_before_connecting():
    stt = SarvamSTT(Settings(sarvam_api_key=""))
    with pytest.raises(ProviderError, match="API key"):
        await stt.begin_utterance()
    await stt.close()


async def test_sarvam_tts_requires_a_key_before_connecting():
    tts = SarvamTTS(Settings(sarvam_api_key=""))
    with pytest.raises(ProviderError, match="API key"):
        async for _chunk in tts.synthesize("hello"):
            pass
    await tts.close()


async def test_provider_close_is_idempotent():
    settings = Settings(llm_provider="echo", sarvam_api_key="test-key")
    providers = [build_llm(settings)[0], SarvamSTT(settings), SarvamTTS(settings)]
    for provider in providers:
        await provider.close()
        await provider.close()
