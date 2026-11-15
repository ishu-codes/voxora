import io
import wave
from types import SimpleNamespace

import numpy as np

from src.voice.core.config import Settings
from src.voice.providers.whisper_stt import (
    WhisperEngine,
    WhisperSTT,
    _select_device,
    decode_audio,
)
from src.voice.services.provider_bundle import ProviderBundle


def _wav_bytes(sample_rate_hz: int) -> bytes:
    samples = (
        np.sin(2 * np.pi * 440 * np.arange(sample_rate_hz) / sample_rate_hz)
        * 0.25
        * 32767
    ).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(samples.tobytes())
    return buffer.getvalue()


def test_decode_wav_resamples_to_16khz_mono_float32():
    audio = decode_audio(_wav_bytes(8_000))

    assert audio.dtype == np.float32
    assert audio.ndim == 1
    assert 15_900 <= audio.size <= 16_100


def test_whisper_is_available_as_an_explicit_stt_provider():
    assert Settings(stt_provider="whisper").stt_provider == "whisper"
    assert Settings().whisper_language == "auto"


def test_unsupported_cuda_device_falls_back_to_cpu():
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: True,
            get_device_capability=lambda: (6, 1),
            get_arch_list=lambda: ["sm_75", "sm_80", "sm_90"],
        )
    )

    assert _select_device(fake_torch) == "cpu"


async def test_provider_bundle_uses_preloaded_whisper_engine():
    bundle = await ProviderBundle.initialize(Settings(stt_provider="whisper"))

    try:
        assert isinstance(await bundle.new_stt(), WhisperSTT)
        assert bundle.whisper_engine is not None
    finally:
        await bundle.close()


def test_decode_does_not_mistake_negative_pcm_sample_for_compressed_audio():
    audio = decode_audio(b"\xff\xe0" * 16_000)

    assert audio.size == 16_000
    assert np.all(audio < 0)


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict]] = []

    def __call__(self, audio: dict, **kwargs):
        self.calls.append((audio, kwargs))
        return {"text": "नमस्ते दुनिया"}


def test_whisper_passes_language_hint_and_shares_pipeline():
    fake_pipeline = FakePipeline()
    engine = WhisperEngine(fake_pipeline, "cpu")
    audio = (np.ones(16_000, dtype=np.float32) * 0.1).tobytes()

    text = engine.transcribe(audio, language="hi-IN")

    assert text == "नमस्ते दुनिया"
    assert fake_pipeline.calls[0][0]["sampling_rate"] == 16_000
    assert fake_pipeline.calls[0][1] == {"language": "hi"}

    engine.transcribe(audio)

    assert fake_pipeline.calls[1][0]["sampling_rate"] == 16_000
    assert fake_pipeline.calls[1][1] == {}


async def test_whisper_session_returns_empty_string_for_silence():
    fake_pipeline = FakePipeline()
    engine = WhisperEngine(fake_pipeline, "cpu")
    stt = WhisperSTT(engine, Settings(stt_provider="whisper"))

    try:
        await stt.begin_utterance()
        await stt.push_audio(b"\x00\x00" * 1_600)
        text = await stt.end_utterance()
    finally:
        await stt.close()
        engine.close()

    assert text == ""
    assert fake_pipeline.calls == []
