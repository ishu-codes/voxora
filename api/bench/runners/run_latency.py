"""Measure the streaming voice loop from recorded user audio to first TTS audio."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import time
from typing import Any

from bench.core.config import load_config
from bench.datasets.scenarios import load_prompt, load_utterances
from bench.providers.base import BenchmarkProviderError
from bench.providers.llm import LLMClient
from bench.providers.sarvam_stt import SarvamSTT
from bench.providers.sarvam_tts import SarvamTTS
from bench.utils.results import new_result_path, utc_stamp, write_json
from src.voice.sentence import SentenceChunker

_TTS_LANGUAGE = {"en": "en-IN", "hi": "hi-IN", "hinglish": "hi-IN"}


def _mixed_utterances(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups = {
        language: [row for row in rows if row["language"] == language]
        for language in ("en", "hi", "hinglish")
    }
    selected: list[dict[str, str]] = []
    for index in range(9):
        selected.append(groups["en"][index])
        if index < 8:
            selected.append(groups["hi"][index])
            selected.append(groups["hinglish"][index])
    return selected


async def _run_turn(
    stt: SarvamSTT,
    tts: SarvamTTS,
    llm: LLMClient,
    prompt: str,
    row: dict[str, str],
    root: Any,
) -> dict[str, Any]:
    stt_result = await stt.transcribe_file(
        str(root / row["wav_path"]),
        row["language"],
        realtime=True,
    )
    audio_end = stt_result.t_audio_end or stt_result.t_final
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": stt_result.text},
    ]
    tts_tasks: list[asyncio.Task[Any]] = []
    first_tts_sent: float | None = None
    first_token: float | None = None
    response_parts: list[str] = []

    def queue_tts(piece: str) -> None:
        nonlocal first_tts_sent
        piece = piece.strip()
        if not piece:
            return
        sent_estimate = time.perf_counter()
        if first_tts_sent is None:
            first_tts_sent = sent_estimate
        tts_tasks.append(
            asyncio.create_task(
                tts.synthesize(
                    piece,
                    _TTS_LANGUAGE.get(row["language"], "en-IN"),
                )
            )
        )

    for attempt in range(4):
        chunker = SentenceChunker(min_chars=1, max_chars=499)
        response_parts.clear()
        first_token = None
        tts_tasks.clear()
        first_tts_sent = None
        async for token, timestamp in llm.stream(messages):
            if first_token is None:
                first_token = timestamp
            response_parts.append(token)
            for sentence in chunker.feed(token):
                queue_tts(sentence)
        if response_parts:
            trailing = chunker.flush()
            if trailing:
                queue_tts(trailing)
            break
        if attempt < 3:
            await asyncio.sleep(2**attempt)
    if not tts_tasks:
        raise BenchmarkProviderError(
            "Agent generated no TTS text after four empty-stream attempts."
        )

    tts_results = await asyncio.gather(*tts_tasks)
    first_audio = min(result.t_first_audio_byte for result in tts_results)
    tts_done = max(result.t_done for result in tts_results)
    if first_token is None or first_tts_sent is None:
        raise BenchmarkProviderError("Streaming response was missing timestamps.")
    stt_final_ms = round((stt_result.t_final - audio_end) * 1000, 1)
    llm_first_token_ms = round(
        (first_token - stt_result.t_final) * 1000,
        1,
    )
    tts_first_audio_ms = round((first_audio - first_tts_sent) * 1000, 1)
    end_to_end_ms = round((first_audio - audio_end) * 1000, 1)
    stage_sum_ms = round(
        stt_final_ms + llm_first_token_ms + tts_first_audio_ms,
        1,
    )
    return {
        "status": "ok",
        "id": row["id"],
        "language": row["language"],
        "reference": row["reference_text"],
        "transcript": stt_result.text,
        "response": "".join(response_parts).strip(),
        "stt_first_partial_ms": (
            round(
                (stt_result.t_first_partial - stt_result.t_request_sent) * 1000,
                1,
            )
            if stt_result.t_first_partial is not None
            else None
        ),
        "stt_final_ms": stt_final_ms,
        "llm_first_token_ms": llm_first_token_ms,
        "tts_first_audio_ms": tts_first_audio_ms,
        "end_to_end_ms": end_to_end_ms,
        "stage_sum_ms": stage_sum_ms,
        "sum_difference_ms": round(end_to_end_ms - stage_sum_ms, 1),
        "tts_done_ms": round((tts_done - audio_end) * 1000, 1),
        "audio_bytes": sum(len(result.audio_bytes) for result in tts_results),
    }


async def _run(args: argparse.Namespace) -> None:
    config = load_config()
    rows = _mixed_utterances(load_utterances())
    if args.limit:
        rows = rows[: args.limit]
    prompt_version = args.prompt or "final"
    prompt = load_prompt(prompt_version)
    latency_config = config.raw["benchmark"]["latency"]
    repeats = int(args.repeats or latency_config["repeats"])
    warmups = (
        int(args.warmup_runs)
        if args.warmup_runs is not None
        else int(latency_config["warmup_runs"])
    )
    stt = SarvamSTT(config, "transcribe")
    tts = SarvamTTS(config)
    llm = LLMClient(
        config,
        config.llm,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        model=config.llm_model,
        temperature=float(config.llm.temperature),
    )
    path = new_result_path("latency", config.root / "results")
    payload: dict[str, Any] = {
        "kind": "latency",
        "run_id": f"latency-{utc_stamp()}",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": platform.platform(),
        "network_region": config.network_region,
        "prompt_version": prompt_version,
        "provider_combination": {
            "stt": f"{stt.name}/{stt.model}",
            "llm": f"{config.llm.provider}/{llm.model}",
            "tts": f"{tts.name}/{tts.model}",
        },
        "utterance_count": len(rows),
        "warmup_runs": warmups,
        "repeats": repeats,
        "timing_definitions": {
            "t0": "perf_counter immediately after the last real-time audio chunk is sent",
            "stt_final_ms": "t0 to final transcript",
            "llm_first_token_ms": "final transcript to first LLM token",
            "tts_first_audio_ms": "first complete sentence sent to TTS to first audio byte",
            "end_to_end_ms": "t0 to first TTS audio byte",
        },
        "rows": [],
    }
    write_json(path, payload)
    try:
        for index in range(warmups):
            row = rows[index % len(rows)]
            print(f"warmup {index + 1}/{warmups}: {row['id']}")
            try:
                await _run_turn(stt, tts, llm, prompt, row, config.root)
            except Exception as exc:
                print(f"  warmup error: {type(exc).__name__}: {exc}")

        for repeat in range(1, repeats + 1):
            for row in rows:
                print(f"latency {repeat}/{repeats}: {row['id']}")
                try:
                    record = await _run_turn(
                        stt,
                        tts,
                        llm,
                        prompt,
                        row,
                        config.root,
                    )
                    record["repeat"] = repeat
                except Exception as exc:
                    record = {
                        "status": "error",
                        "id": row["id"],
                        "language": row["language"],
                        "repeat": repeat,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    print(f"  error: {record['error']}")
                payload["rows"].append(record)
                write_json(path, payload)
    finally:
        await stt.close()
        await tts.close()
        await llm.close()
    payload["finished_at_utc"] = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(),
    )
    payload["failure_count"] = sum(
        1 for row in payload["rows"] if row["status"] == "error"
    )
    payload["sum_difference_gt_50ms"] = [
        {
            "id": row["id"],
            "repeat": row["repeat"],
            "difference_ms": row["sum_difference_ms"],
        }
        for row in payload["rows"]
        if row["status"] == "ok"
        and abs(float(row.get("sum_difference_ms", 0))) > 50
    ]
    write_json(path, payload)
    print(json.dumps({"path": str(path), "failures": payload["failure_count"]}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt",
        default="final",
        choices=["v1", "v2", "v3", "v4", "final"],
    )
    parser.add_argument("--limit", type=int, help="Run only the first N selected utterances")
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--warmup-runs", type=int)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
