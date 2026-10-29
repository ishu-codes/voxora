"""Run clean, phone, pink-noise, and babble STT conditions."""

from __future__ import annotations

import argparse
from argparse import Namespace

from bench.core.config import ROOT
from bench.runners.make_noisy import CONDITIONS, generate
from bench.runners.run_stt import _run as run_stt


async def main_async(generate_first: bool) -> None:
    if generate_first:
        generate(ROOT)
    for condition in CONDITIONS:
        if condition == "clean":
            print("=== Reusing completed clean STT baseline ===")
            continue
        args = Namespace(
            providers=[
                "sarvam",
                "faster-whisper",
                "faster-whisper-nohint",
            ],
            modes=["transcribe", "codemix", "translit"],
            limit=None,
            wav_dir=f"data/wav_noisy/{condition}",
            condition=condition,
        )
        print(f"\n=== STT condition: {condition} ===")
        await run_stt(args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    import asyncio

    asyncio.run(main_async(args.generate))


if __name__ == "__main__":
    main()
