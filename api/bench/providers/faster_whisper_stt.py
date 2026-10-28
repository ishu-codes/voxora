"""Local Faster Whisper speech-to-text adapter."""

from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

from bench.core.config import BenchmarkConfig
from bench.providers.base import BenchmarkProviderError, STTResult
from bench.utils.audio import convert_to_pcm16_mono

_MODEL_CACHE:dict[tuple[str, str, str], Any] = {}


def _best_compute(ctranslate2: Any) -> tuple[str, str]:
    try:
        if ctranslate2.get_cuda_device_count() > 0:
            supported = ctranslate2.get_supported_compute_types("cuda")
            if "float16" in supported:
                return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


class FasterWhisperSTT:
    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        use_language_hint: bool = True,
        model_size: str | None = None,
    ) -> None:
        self.config = config
        self.use_language_hint = use_language_hint
        self.model = model_size or str(config.faster_whisper["model"])
        self.mode = "transcribe" if use_language_hint else "transcribe-no-hint"
        self.name = f"faster-whisper-{self.model}"
        self.beam_size = int(config.faster_whisper["beam_size"])
        self._model: Any = None
        self._device = "cpu"
        self._compute_type = "int8"

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            import ctranslate2
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise BenchmarkProviderError(
                "faster-whisper is not installed. Run `uv sync`."
            ) from exc
        self._device, self._compute_type = _best_compute(ctranslate2)
        download_root = self.config.root / str(
            self.config.faster_whisper["download_root"]
        )
        download_root.mkdir(parents=True, exist_ok=True)
        key = (self.model, self._device, self._compute_type)
        if key not in _MODEL_CACHE:
            _MODEL_CACHE[key] = WhisperModel(
                self.model,
                device=self._device,
                compute_type=self._compute_type,
                download_root=str(download_root),
            )
        self._model = _MODEL_CACHE[key]
        return self._model

    def metadata(self, language_hint: str | None) -> dict[str, Any]:
        return {
            "device": self._device,
            "compute_type": self._compute_type,
            "model_size": self.model,
            "beam_size": self.beam_size,
            "language_hint": (
                {"en": "en", "hi": "hi", "hinglish": "hi"}.get(
                    language_hint or ""
                )
                if self.use_language_hint
                else None
            ),
        }

    async def transcribe_file(
        self,
        wav_path: str,
        language_hint: str | None,
    ) -> STTResult:
        audio = convert_to_pcm16_mono(wav_path, self.config.sample_rate)
        samples = (
            np.frombuffer(audio.pcm, dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        hint = (
            {"en": "en", "hi": "hi", "hinglish": "hi"}.get(
                language_hint or ""
            )
            if self.use_language_hint
            else None
        )
        request_sent = time.perf_counter()
        try:
            model = self._load_model()
            segments, _ = model.transcribe(
                samples,
                language=hint,
                beam_size=self.beam_size,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            text = "".join(segment.text for segment in segments).strip()
        except BenchmarkProviderError:
            raise
        except Exception as exc:
            raise BenchmarkProviderError(
                f"Faster Whisper failed: {exc}\n{traceback.format_exc()}"
            ) from exc
        finished = time.perf_counter()
        return STTResult(
            text=text,
            t_request_sent=request_sent,
            t_first_partial=None,
            t_final=finished,
            provider=self.name,
            model=self.model,
            mode=self.mode,
        )

    async def close(self) -> None:
        self._model = None


__all__ = ["FasterWhisperSTT"]
