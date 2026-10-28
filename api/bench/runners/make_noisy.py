"""Generate deterministic phone and noise conditions for every utterance."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from bench.core.config import ROOT

CONDITIONS = ("clean", "phone", "pink_20db", "pink_10db", "pink_5db", "babble_10db")
SEED = 20261022


def _read_float(path: Path) -> tuple[int, np.ndarray]:
    rate, data = wavfile.read(path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    else:
        data = data.astype(np.float64)
    return int(rate), data


def _write(path: Path, rate: int, data: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(data, -1.0, 1.0)
    wavfile.write(path, rate, (clipped * 32767.0).astype(np.int16))


def _pink_noise(length: int, rng: np.random.Generator) -> np.ndarray:
    white = rng.normal(size=length)
    spectrum = np.fft.rfft(white)
    frequencies = np.fft.rfftfreq(length, d=1.0 / 16000.0)
    scale = np.ones_like(frequencies)
    scale[1:] = 1.0 / np.sqrt(frequencies[1:])
    pink = np.fft.irfft(spectrum * scale, n=length)
    pink -= pink.mean()
    return pink / max(np.sqrt(np.mean(pink**2)), 1e-12)


def _mix_snr(signal_data: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    signal_power = np.mean(signal_data**2)
    noise_power = np.mean(noise**2)
    target_noise_power = signal_power / (10 ** (snr_db / 10.0))
    scaled = noise * np.sqrt(target_noise_power / max(noise_power, 1e-12))
    return signal_data + scaled


def _mu_law_roundtrip(data: np.ndarray) -> np.ndarray:
    mu = 255.0
    magnitude = np.log1p(mu * np.abs(data)) / np.log1p(mu)
    encoded = np.round(magnitude * 127.0).astype(np.int16)
    decoded = np.sign(data) * ((1.0 + mu) ** (np.abs(encoded) / 127.0) - 1.0) / mu
    return decoded


def _phone(data: np.ndarray) -> tuple[int, np.ndarray]:
    sos = signal.butter(6, [300, 3400], btype="bandpass", fs=16000, output="sos")
    filtered = signal.sosfiltfilt(sos, data)
    downsampled = signal.resample_poly(filtered, up=1, down=2)
    return 8000, _mu_law_roundtrip(downsampled)


def generate(root: Path = ROOT) -> list[Path]:
    source_dir = root / "data" / "wav"
    output_root = root / "data" / "wav_noisy"
    sources = sorted(source_dir.glob("*.wav"))
    rng = np.random.default_rng(SEED)
    loaded = {path.stem: _read_float(path) for path in sources}
    written: list[Path] = []

    for condition in CONDITIONS:
        for index, source in enumerate(sources):
            destination = output_root / condition / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if condition == "clean":
                shutil.copyfile(source, destination)
                written.append(destination)
                continue
            rate, data = loaded[source.stem]
            if condition == "phone":
                out_rate, transformed = _phone(data)
            else:
                out_rate = rate
                if condition.startswith("pink"):
                    snr = float(condition.removeprefix("pink_").removesuffix("db"))
                    transformed = _mix_snr(data, _pink_noise(len(data), rng), snr)
                else:
                    others = [
                        loaded[other.stem][1]
                        for other in sources
                        if other.stem != source.stem
                    ][(index % 3) : (index % 3) + 3]
                    babble = np.zeros_like(data)
                    for item in others:
                        if len(item) < len(data):
                            item = np.pad(item, (0, len(data) - len(item)))
                        babble += item[: len(data)] / 3.0
                    transformed = _mix_snr(data, babble, 10.0)
            _write(destination, out_rate, transformed)
            written.append(destination)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    paths = generate(args.root)
    print(f"Generated {len(paths)} wav files under {args.root / 'data' / 'wav_noisy'}")


if __name__ == "__main__":
    main()
