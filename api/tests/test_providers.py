from src.voice.config import Settings
from src.voice.providers import build_llm, build_stt, build_tts
from src.voice.providers.llm import EchoLLM, OpenAICompatibleLLM
from src.voice.providers.stt import BrowserSTT, OpenAICompatibleSTT
from src.voice.providers.tts import BrowserTTS, OpenAITTS


def test_auto_falls_back_to_zero_key_providers(monkeypatch):
    for name in ("LLM_API_KEY", "STT_API_KEY", "TTS_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert isinstance(build_llm(settings)[0], EchoLLM)
    assert isinstance(build_stt(settings)[0], BrowserSTT)
    assert isinstance(build_tts(settings)[0], BrowserTTS)


def test_explicit_openai_adapters_build_without_network():
    settings = Settings(
        stt_provider="openai",
        llm_provider="openai",
        tts_provider="openai",
        llm_api_key="test-key",
    )
    stt, _ = build_stt(settings)
    llm, _ = build_llm(settings)
    tts, _ = build_tts(settings)
    assert isinstance(stt, OpenAICompatibleSTT)
    assert isinstance(llm, OpenAICompatibleLLM)
    assert isinstance(tts, OpenAITTS)
    assert tts.kind == "audio"
    assert tts.sample_rate == settings.tts_sample_rate


def test_ollama_preset_uses_local_base_url():
    settings = Settings(
        llm_provider="ollama",
        llm_base_url="http://localhost:11434/v1",
        llm_model="llama3.2",
    )
    llm, _ = build_llm(settings)
    assert isinstance(llm, OpenAICompatibleLLM)


async def test_provider_close_is_idempotent():
    settings = Settings(tts_provider="browser", llm_provider="echo", stt_provider="browser")
    providers = [build_stt(settings)[0], build_llm(settings)[0], build_tts(settings)[0]]
    for provider in providers:
        await provider.close()
        await provider.close()
