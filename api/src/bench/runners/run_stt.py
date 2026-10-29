"""Run every configured STT provider/mode over the recorded utterance corpus."""

from __future__ import annotations

import argparse
import asyncio
import platform
import time
from pathlib import Path
from typing import Any

import jiwer

from bench.core.config import load_config
from bench.datasets.scenarios import load_utterances
from bench.evaluation.judge import build_classifier
from bench.evaluation.stt_metrics import classify_stt_records
from bench.providers.base import BenchmarkProviderError
from bench.providers.faster_whisper_stt import FasterWhisperSTT
from bench.providers.sarvam_stt import SarvamSTT
from bench.providers.whisper_stt import WhisperSTT
from bench.utils.audio import wav_properties
from bench.utils.normalize import detect_script, normalize_text, parse_entities
from bench.utils.results import new_result_path, utc_stamp, write_json


def _score(reference: str, hypothesis: str) -> tuple[float, float]:
    try:
        word_error = float(jiwer.wer(reference, hypothesis))
    except (ValueError, ZeroDivisionError):
        word_error = 1.0
    try:
        char_error = float(jiwer.cer(reference, hypothesis))
    except (ValueError, ZeroDivisionError):
        char_error = 1.0
    return round(word_error, 6), round(char_error, 6)


async def _run(args: argparse.Namespace) -> Path:
    config = load_config()
    rows = load_utterances()
    if args.limit:
        rows = rows[: args.limit]

    modes = args.modes or list(config.stt["modes"])
    providers: list[Any] = []
    if "sarvam" in args.providers:
        providers.extend(SarvamSTT(config, mode) for mode in modes)
    if "openai-whisper" in args.providers or "whisper" in args.providers:
        providers.append(WhisperSTT(config))
    if "faster-whisper" in args.providers:
        providers.append(FasterWhisperSTT(config, use_language_hint=True))
    if "faster-whisper-nohint" in args.providers:
        providers.append(FasterWhisperSTT(config, use_language_hint=False))
    classifier_client = build_classifier(config)

    result_path = new_result_path("stt", config.root / "results")
    payload: dict[str, Any] = {
        "kind": "stt",
        "run_id": f"stt-{utc_stamp()}",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": platform.platform(),
        "network_region": config.network_region,
        "sample_rate_hz": config.sample_rate,
        "normalization": "NFC, lowercase, punctuation removal, numerals to English words, Devanagari to Latin",
        "utterance_count": len(rows),
        "providers_requested": args.providers,
        "condition": args.condition,
        "wav_root": args.wav_dir,
        "classifier": {
            "model": classifier_client.model,
            "endpoint": classifier_client.endpoint,
            "max_questions_per_call": 5,
        },
        "rows": [],
    }
    write_json(result_path, payload)

    try:
        for provider in providers:
            provider_records: list[dict[str, Any]] = []
            print(
                f"STT provider={provider.name} model={provider.model} "
                f"mode={provider.mode}"
            )
            for index, row in enumerate(rows, 1):
                wav_root = config.root / args.wav_dir
                wav_path = wav_root / f"{row['id']}.wav"
                input_rate = wav_properties(wav_path)[0]
                reference_normalized = normalize_text(row["reference_text"])
                record: dict[str, Any] = {
                    "id": row["id"],
                    "wav_path": str(wav_path.relative_to(config.root)),
                    "reference": row["reference_text"],
                    "reference_normalized": reference_normalized,
                    "language": row["language"],
                    "script": row["script"],
                    "category": row["category"],
                    "entities": parse_entities(row["entities"]),
                    "condition": args.condition,
                    "provider": provider.name,
                    "model": provider.model,
                    "mode": provider.mode,
                    "reference_script": row["script"],
                    "input_sample_rate_hz": input_rate,
                }
                if hasattr(provider, "metadata"):
                    record.update(provider.metadata(row["language"]))
                if provider.name == "sarvam" and input_rate == 8000:
                    record["declared_sample_rate_hz"] = 8000
                try:
                    result = await provider.transcribe_file(
                        str(wav_path),
                        row["language"],
                    )
                    hypothesis_normalized = normalize_text(result.text)
                    output_script = detect_script(result.text)
                    comparable = output_script == row["script"]
                    if comparable:
                        word_error, char_error = _score(
                            reference_normalized,
                            hypothesis_normalized,
                        )
                    else:
                        word_error = char_error = None
                    record.update(
                        {
                            "status": "ok",
                            "raw_hypothesis": result.text,
                            "normalized_hypothesis": hypothesis_normalized,
                            "output_script": output_script,
                            "wer_comparable": comparable,
                            "wer": word_error,
                            "cer": char_error,
                            "empty_transcript": not bool(result.text.strip()),
                            "stt_first_partial_ms": (
                                round(
                                    (result.t_first_partial - result.t_request_sent)
                                    * 1000,
                                    1,
                                )
                                if result.t_first_partial is not None
                                else None
                            ),
                            "stt_final_ms": round(
                                (result.t_final - result.t_request_sent) * 1000,
                                1,
                            ),
                        }
                    )
                    print(
                        f"  {index:>2}/{len(rows)} {row['id']} "
                        f"script={output_script} "
                        f"WER={word_error if word_error is not None else 'n/a'}"
                    )
                except (BenchmarkProviderError, Exception) as exc:
                    record.update(
                        {
                            "status": "error",
                            "raw_hypothesis": "",
                            "normalized_hypothesis": "",
                            "output_script": "empty",
                            "wer_comparable": False,
                            "wer": None,
                            "cer": None,
                            "empty_transcript": None,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    print(
                        f"  {index:>2}/{len(rows)} {row['id']} "
                        f"ERROR {type(exc).__name__}: {exc}"
                    )
                provider_records.append(record)
                payload["rows"].append(record)
                write_json(result_path, payload)
            valid_records = [
                record for record in provider_records if record["status"] == "ok"
            ]
            classify_stt_records(classifier_client, valid_records)
            for record in provider_records:
                if record["status"] != "ok":
                    record["semantic_match"] = False
                    record["semantic_probability"] = None
                    record["entity_checks"] = []
                    record["entity_accuracy"] = None
            write_json(result_path, payload)
    finally:
        for provider in providers:
            await provider.close()

    payload["finished_at_utc"] = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(),
    )
    payload["failure_count"] = sum(
        1 for row in payload["rows"] if row["status"] == "error"
    )
    write_json(result_path, payload)
    print(f"Wrote {result_path}")
    return result_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=[
            "sarvam",
            "whisper",
            "openai-whisper",
            "faster-whisper",
            "faster-whisper-nohint",
        ],
        default=["sarvam"],
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["transcribe", "codemix", "translit"],
    )
    parser.add_argument("--limit", type=int, help="Run only the first N utterances")
    parser.add_argument("--wav-dir", default="data/wav")
    parser.add_argument("--condition", default="clean")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
