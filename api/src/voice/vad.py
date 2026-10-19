"""Frame-based voice activity detection and endpointing.

The default detector is deliberately dependency-free: it tracks an adaptive
noise floor and uses short energy frames to find speech starts and ends.  The
``VAD`` protocol makes it possible to swap in Silero or a provider-native
detector without touching the pipeline.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from .audio import pcm16_rms
from .config import FRAME_MS


@dataclass(slots=True)
class VADEvent:
    kind: str  # "speech_start" | "speech_end"
    audio: bytes = b""
    duration_ms: float = 0.0


class VAD(Protocol):
    is_speech: bool

    def process(self, frame: bytes) -> list[VADEvent]: ...

    def reset(self) -> None: ...


@dataclass
class EnergyVAD:
    """Energy VAD with hysteresis, pre-roll and a configurable hangover.

    The noise floor adapts only while the detector is idle, which keeps a
    steady fan or air-conditioner from being classified as speech.
    """

    threshold: float = 0.014
    start_frames: int = 3
    end_silence_ms: int = 650
    pre_roll_ms: int = 300
    max_utterance_ms: int = 30_000
    adaptive_noise_floor: bool = True

    is_speech: bool = field(default=False, init=False)
    _noise_floor: float = field(default=0.004, init=False)
    _voiced_run: int = field(default=0, init=False)
    _silence_ms: int = field(default=0, init=False)
    _utterance_ms: float = field(default=0, init=False)
    _utterance: bytearray = field(default_factory=bytearray, init=False)
    _pre_roll: deque[bytes] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._pre_roll = deque(maxlen=max(1, self.pre_roll_ms // FRAME_MS))

    @property
    def effective_threshold(self) -> float:
        return max(self.threshold, self._noise_floor * 2.5)

    def reset(self) -> None:
        self.is_speech = False
        self._voiced_run = 0
        self._silence_ms = 0
        self._utterance_ms = 0
        self._utterance.clear()
        self._pre_roll.clear()

    def process(self, frame: bytes) -> list[VADEvent]:
        if not frame:
            return []

        rms = pcm16_rms(frame)
        voiced = rms >= self.effective_threshold
        events: list[VADEvent] = []

        if not self.is_speech:
            self._pre_roll.append(frame)
            if self.adaptive_noise_floor and not voiced:
                # Slow exponential average: 2 % per idle frame.
                self._noise_floor = (self._noise_floor * 0.98) + (rms * 0.02)
                self._noise_floor = min(max(self._noise_floor, 0.001), self.threshold)

            self._voiced_run = self._voiced_run + 1 if voiced else 0
            if self._voiced_run >= self.start_frames:
                self.is_speech = True
                self._silence_ms = 0
                self._utterance_ms = 0.0
                self._utterance = bytearray(b"".join(self._pre_roll))
                events.append(
                    VADEvent("speech_start", duration_ms=self._utterance_ms)
                )
            return events

        # In speech: every frame (including trailing silence) belongs to the
        # utterance so the STT adapter receives a natural tail.
        self._utterance.extend(frame)
        self._utterance_ms += FRAME_MS

        if voiced:
            self._silence_ms = 0
        else:
            self._silence_ms += FRAME_MS

        if self._silence_ms >= self.end_silence_ms or self._utterance_ms >= self.max_utterance_ms:
            audio = bytes(self._utterance)
            duration = self._utterance_ms
            self.is_speech = False
            self._voiced_run = 0
            self._silence_ms = 0
            self._utterance_ms = 0
            self._utterance.clear()
            self._pre_roll.clear()
            events.append(VADEvent("speech_end", audio=audio, duration_ms=duration))

        return events


__all__ = ["VAD", "VADEvent", "EnergyVAD"]
