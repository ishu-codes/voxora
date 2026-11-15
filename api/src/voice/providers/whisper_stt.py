"""Local OpenAI Whisper speech-to-text adapter."""

from __future__ import annotations

import asyncio
import io
import logging
import math
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from ..core.config import SAMPLE_RATE, Settings
from .base import PartialCallback, ProviderError

logger = logging.getLogger(__name__)

WHISPER_MODEL = "openai/whisper-base"
_SILENCE_RMS = 1e-5


def _resample(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    if sample_rate == SAMPLE_RATE or audio.size == 0:
        return audio.astype(np.float32, copy=False)

    from scipy.signal import resample_poly

    divisor = math.gcd(sample_rate, SAMPLE_RATE)
    return resample_poly(
        audio,
        SAMPLE_RATE // divisor,
        sample_rate // divisor,
    ).astype(np.float32, copy=False)


def _mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio.astype(np.float32, copy=False)
    return audio.mean(axis=1, dtype=np.float32)


def _decode_wav(audio_bytes: bytes) -> np.ndarray:
    import soundfile as sf

    try:
        audio, sample_rate = sf.read(
            io.BytesIO(audio_bytes),
            dtype="float32",
            always_2d=True,
        )
    except Exception as exc:
        raise ProviderError("stt", f"Could not decode WAV audio: {exc}") from exc
    return _resample(_mono(audio), sample_rate)


def _decode_with_ffmpeg(audio_bytes: bytes) -> np.ndarray:
    if shutil.which("ffmpeg") is None:
        raise ProviderError(
            "stt",
            "ffmpeg is required to decode this audio format.",
        )
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                str(SAMPLE_RATE),
                "pipe:1",
            ],
            input=audio_bytes,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderError("stt", f"Could not run ffmpeg: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProviderError("stt", f"Could not decode audio with ffmpeg: {detail}")
    return np.frombuffer(result.stdout, dtype="<i2").astype(np.float32) / 32768.0


def _is_wav(audio_bytes: bytes) -> bool:
    return (
        len(audio_bytes) >= 12
        and audio_bytes[:4] == b"RIFF"
        and audio_bytes[8:12] == b"WAVE"
    )


def _is_encoded_audio(audio_bytes: bytes) -> bool:
    header = audio_bytes[:12]
    return (
        header.startswith(b"ID3")
        or header.startswith(b"fLaC")
        or header.startswith(b"OggS")
        or header.startswith(b"\x1aE\xdf\xa3")
        or header.startswith(b"FORM")
        or header.startswith(b"#!AMR")
        or header.startswith(b"caff")
        or (len(header) >= 8 and header[4:8] == b"ftyp")
    )


def decode_audio(audio_bytes: bytes) -> np.ndarray:
    """Decode WAV or 16 kHz PCM16 mono audio to float32 at 16 kHz."""
    if not audio_bytes:
        return np.empty(0, dtype=np.float32)
    if _is_wav(audio_bytes):
        audio = _decode_wav(audio_bytes)
    elif _is_encoded_audio(audio_bytes):
        audio = _decode_with_ffmpeg(audio_bytes)
    else:
        pcm = audio_bytes[: len(audio_bytes) - (len(audio_bytes) % 2)]
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0

    audio = np.nan_to_num(audio, copy=False)
    return np.clip(audio, -1.0, 1.0).astype(np.float32, copy=False)


def _language_hint(language: str | None) -> str | None:
    value = (language or "").strip().lower()
    if not value or value == "auto":
        return None
    if value == "hinglish":
        return "hi"
    return value.replace("_", "-").split("-", 1)[0] or None


def _select_device(torch_module: Any) -> str:
    if not torch_module.cuda.is_available():
        return "cpu"
    try:
        major, minor = torch_module.cuda.get_device_capability()
        supported = {
            arch.lower() for arch in torch_module.cuda.get_arch_list()
        }
        target = f"sm_{major}{minor}"
        if supported and not any(arch.startswith(target) for arch in supported):
            logger.warning(
                "CUDA device capability %s is unsupported by installed PyTorch; "
                "using CPU",
                target,
            )
            return "cpu"
    except Exception:
        logger.warning("Could not validate CUDA compatibility; using CPU")
        return "cpu"
    return "cuda"


class WhisperEngine:
    """Process-wide Whisper pipeline loaded during FastAPI startup."""

    def __init__(self, pipeline: Any, device: str) -> None:
        self._pipeline = pipeline
        self.device = device
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="whisper-stt",
        )

    @classmethod
    def load(cls) -> "WhisperEngine":
        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:
            raise ProviderError(
                "stt",
                "Local Whisper dependencies are not installed. "
                "Install the backend requirements.",
            ) from exc

        device = _select_device(torch)
        asr = pipeline(
            "automatic-speech-recognition",
            model=WHISPER_MODEL,
            device=0 if device == "cuda" else -1,
        )
        logger.info("local whisper loaded model=%s device=%s", WHISPER_MODEL, device)
        return cls(asr, device)

    def transcribe(self, audio_bytes: bytes, language: str | None = None) -> str:
        audio = decode_audio(audio_bytes)
        if audio.size == 0:
            return ""
        if float(np.sqrt(np.mean(np.square(audio), dtype=np.float64))) < _SILENCE_RMS:
            return ""

        kwargs: dict[str, Any] = {}
        hint = _language_hint(language)
        if hint is not None:
            kwargs["language"] = hint
        result = self._pipeline(
            {"raw": audio, "sampling_rate": SAMPLE_RATE},
            **kwargs,
        )
        if isinstance(result, list):
            text = " ".join(str(item.get("text", "")) for item in result)
        elif isinstance(result, dict):
            text = str(result.get("text", ""))
        else:
            text = str(result)
        return text.strip()

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)


class WhisperSTT:
    """Session adapter that buffers one VAD-bounded turn for local Whisper."""

    name = "whisper"
    supports_partials = False

    def __init__(
        self,
        engine: WhisperEngine,
        settings: Settings,
        session_id: str = "",
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._tag = f"session={session_id[:8]}" if session_id else "session=?"
        self._audio = bytearray()
        self._active = False

    @property
    def language(self) -> str:
        return self._settings.whisper_language

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._engine._executor,
            self._engine.transcribe,
            audio_bytes,
            language,
        )

    async def begin_utterance(self, on_partial: PartialCallback | None = None) -> None:
        self._audio.clear()
        self._active = True
        logger.info("%s stt begin utterance provider=whisper", self._tag)

    async def push_audio(self, pcm: bytes) -> None:
        if self._active and pcm:
            self._audio.extend(pcm)

    async def end_utterance(self) -> str:
        if not self._active:
            return ""
        self._active = False
        audio = bytes(self._audio)
        self._audio.clear()
        if not audio or not any(audio):
            logger.info("%s stt final provider=whisper empty audio", self._tag)
            return ""
        try:
            text = await self.transcribe(audio, self.language)
        except ProviderError:
            raise
        except Exception as exc:
            logger.exception("%s stt local whisper failed", self._tag)
            raise ProviderError("stt", f"Whisper transcription failed: {exc}") from exc
        logger.info(
            "%s stt final provider=whisper audio_bytes=%d chars=%d",
            self._tag,
            len(audio),
            len(text),
        )
        return text

    async def cancel_utterance(self) -> None:
        self._active = False
        self._audio.clear()

    async def close(self) -> None:
        await self.cancel_utterance()


__all__ = [
    "WHISPER_MODEL",
    "WhisperEngine",
    "WhisperSTT",
    "decode_audio",
]
