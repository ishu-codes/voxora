import struct

from src.voice.audio.vad import EnergyVAD
from src.voice.core.config import FRAME_BYTES


def _frame(amplitude: float) -> bytes:
    value = int(max(-1.0, min(1.0, amplitude)) * 32767)
    samples = FRAME_BYTES // 2
    return struct.pack("<h", value) * samples


def _speak(vad: EnergyVAD, frames: int = 4) -> list:
    events = []
    for _ in range(frames):
        events.extend(vad.process(_frame(0.3)))
    return events


def _silence(vad: EnergyVAD, frames: int) -> list:
    events = []
    for _ in range(frames):
        events.extend(vad.process(_frame(0.0)))
    return events


def test_detects_speech_start_and_end():
    vad = EnergyVAD(threshold=0.01, start_frames=2, end_silence_ms=40, pre_roll_ms=40)
    assert _silence(vad, 5) == []
    assert vad.is_speech is False

    start_events = _speak(vad, 2)
    assert [event.kind for event in start_events] == ["speech_start"]
    assert start_events[0].audio, "pre-roll audio should accompany the start event"
    assert vad.is_speech is True

    end_events = _silence(vad, 2)
    assert [event.kind for event in end_events] == ["speech_end"]
    assert end_events[0].audio
    assert end_events[0].duration_ms > 0
    assert vad.is_speech is False


def test_pre_roll_is_included_in_utterance():
    vad = EnergyVAD(threshold=0.01, start_frames=1, end_silence_ms=20, pre_roll_ms=40)
    _silence(vad, 1)
    _speak(vad, 1)
    events = _silence(vad, 1)
    speech_end = events[0]
    # One pre-roll frame plus the voiced frame plus the trailing silent frame.
    assert len(speech_end.audio) >= FRAME_BYTES * 3


def test_silence_below_threshold_does_not_trigger():
    vad = EnergyVAD(threshold=0.05, start_frames=3, end_silence_ms=40, pre_roll_ms=40)
    events = []
    for _ in range(10):
        events.extend(vad.process(_frame(0.005)))
    assert events == []


def test_max_utterance_forces_endpoint():
    vad = EnergyVAD(
        threshold=0.01, start_frames=1, end_silence_ms=10_000, pre_roll_ms=20, max_utterance_ms=60
    )
    events = _speak(vad, 4)
    kinds = [event.kind for event in events]
    assert "speech_start" in kinds
    assert "speech_end" in kinds
