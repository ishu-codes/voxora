"""Run one live Gnani Prisma -> current LLM -> Gnani Timbre round trip."""

from __future__ import annotations

import asyncio
import json
import time
import wave
from dataclasses import replace
from pathlib import Path

import numpy as np

from src.voice.core.config import Settings
from src.voice.providers.gnani_stt import GnaniSTT
from src.voice.providers.gnani_tts import GnaniTTS
from src.voice.providers.llm import build_llm
from src.voice.providers.whisper_stt import decode_audio

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    settings = Settings.from_env()
    if not settings.gnani_api_key:
        raise SystemExit("GNANI_API_KEY is not configured in api/.env")
    audio_path = ROOT / "data" / "wav" / "hg03.wav"
    pcm = (
        np.clip(decode_audio(audio_path.read_bytes()), -1.0, 1.0) * 32767
    ).astype("<i2").tobytes()

    stt = GnaniSTT(
        replace(
            settings,
            stt_provider="gnani",
            gnani_stt_language="hi-IN",
            gnani_stt_format="verbatim",
        ),
        "verify-stt",
    )
    await stt.begin_utterance()
    for offset in range(0, len(pcm), 1_024):
        frame = pcm[offset : offset + 1_024]
        if len(frame) < 1_024:
            frame += b"\x00" * (1_024 - len(frame))
        await stt.push_audio(frame)
        await asyncio.sleep(0.032)
    transcript = await stt.end_utterance()
    await stt.close()

    llm, reason = build_llm(settings)
    llm_started = time.perf_counter()
    reply_parts: list[str] = []
    async for token in llm.stream(
        [
            {
                "role": "system",
                "content": (
                    "Reply in one short spoken sentence. Acknowledge the "
                    "customer's payment date without inventing details."
                ),
            },
            {"role": "user", "content": transcript},
        ]
    ):
        reply_parts.append(token)
    llm_ms = round((time.perf_counter() - llm_started) * 1000, 1)
    reply = "".join(reply_parts).strip()
    await llm.close()

    tts = GnaniTTS(settings, "verify-tts")
    prewarm = asyncio.create_task(tts.prepare(settings.gnani_tts_voice))
    await asyncio.sleep(0.01)
    tts_started = time.perf_counter()
    audio = bytearray()
    first_audio_ms: float | None = None
    async for chunk in tts.synthesize(reply, settings.gnani_tts_voice):
        if first_audio_ms is None:
            first_audio_ms = round((time.perf_counter() - tts_started) * 1000, 1)
        audio.extend(chunk)
    await prewarm
    await tts.close()

    output_path = Path("/tmp/voxora-gnani-roundtrip.wav")
    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(settings.tts_sample_rate)
        output.writeframes(audio)

    print(
        json.dumps(
            {
                "audio_input": str(audio_path.relative_to(ROOT)),
                "prisma_transcript": transcript,
                "llm_provider": llm.name,
                "llm_reason": reason,
                "llm_reply": reply,
                "llm_ms": llm_ms,
                "timbre_voice": settings.gnani_tts_voice,
                "timbre_first_audio_ms": first_audio_ms,
                "timbre_audio_bytes": len(audio),
                "output_wav": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
