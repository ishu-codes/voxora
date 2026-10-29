"""Record missing benchmark utterances as 16 kHz mono PCM WAV files."""

from __future__ import annotations

import argparse
import csv
import sys
import threading
from pathlib import Path

from bench.core.config import ROOT


def _load_rows() -> list[dict[str, str]]:
    with (ROOT / "data" / "utterances.csv").open(
        newline="",
        encoding="utf-8",
    ) as handle:
        return list(csv.DictReader(handle))


def _record(device: int | None) -> tuple[object, int]:
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise SystemExit(
            "Recording requires sounddevice and numpy. "
            "Install them with `uv sync --group dev`."
        ) from exc

    chunks: list[object] = []

    def callback(indata: object, frames: int, time_info: object, status: object) -> None:
        if status:
            print(f"Audio warning: {status}", file=sys.stderr)
        chunks.append(indata.copy())

    stop = threading.Event()

    def wait_for_enter() -> None:
        try:
            input()
        except EOFError:
            pass
        stop.set()

    threading.Thread(target=wait_for_enter, daemon=True).start()
    with sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype="float32",
        device=device,
        callback=callback,
    ):
        print("Recording. Press Enter when you finish the sentence.")
        stop.wait()
    audio = np.concatenate(chunks, axis=0)[:, 0] if chunks else np.zeros(0)
    return audio, 16000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", type=int)
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="ID",
        help="Record only these utterance ids.",
    )
    parser.add_argument(
        "--redo",
        nargs="+",
        metavar="ID",
        help="Overwrite these existing ids.",
    )
    parser.add_argument("--list-devices", action="store_true")
    args = parser.parse_args()

    try:
        import sounddevice as sd
        import soundfile as sf
    except ImportError as exc:
        raise SystemExit(
            "Recording requires sounddevice and soundfile. "
            "Install them with `uv sync --group dev`."
        ) from exc
    if args.list_devices:
        print(sd.query_devices())
        return

    rows = _load_rows()
    only = set(args.only or [])
    redo = set(args.redo or [])
    for row in rows:
        utterance_id = row["id"]
        if only and utterance_id not in only:
            continue
        output = ROOT / row["wav_path"]
        if output.exists() and utterance_id not in redo:
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        print(f"\n{utterance_id} ({row['language']}, {row['category']})")
        print(row["reference_text"])
        input("Press Enter to record, or type q and Enter to stop: ")
        audio, sample_rate = _record(args.device)
        if len(audio) == 0:
            print("No audio captured; skipped.")
            continue
        sf.write(output, audio, sample_rate, subtype="PCM_16")
        print(f"Saved {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
