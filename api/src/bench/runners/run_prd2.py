"""Run the PRD2 STT and TTS benchmarks without invoking the LLM."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import jiwer

from bench.core.config import ROOT, BenchmarkConfig, load_config
from bench.datasets.scenarios import load_utterances
from bench.providers.base import BenchmarkProviderError
from bench.providers.faster_whisper_stt import FasterWhisperSTT
from bench.providers.gnani_stt import GnaniSTT
from bench.providers.gnani_tts import GnaniTTS
from bench.providers.sarvam_stt import SarvamSTT
from bench.providers.sarvam_tts import SarvamTTS
from bench.utils.audio import wav_properties
from bench.utils.normalize import normalize_text
from bench.utils.results import utc_stamp, write_json

RESULTS_ROOT = ROOT / "results" / "prd2"
CONDITIONS = ("clean", "phone", "pink_20db", "pink_10db", "pink_5db", "babble_10db")
TTS_TEXTS_PATH = ROOT / "data" / "prd2_tts_texts.json"
NORMALIZATION_DESCRIPTION = (
    "Unicode NFC; lowercase; punctuation and symbols removed; Arabic and "
    "Devanagari digits converted to English number words; Devanagari "
    "deterministically transliterated to Latin using the repository mapping; "
    "whitespace collapsed. The same normalization is applied to every provider."
)


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 6)
    rank = (len(ordered) - 1) * p / 100
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 6)


def _score(reference: str, hypothesis: str) -> tuple[float, float]:
    reference = normalize_text(reference)
    hypothesis = normalize_text(hypothesis)
    if not hypothesis:
        return 1.0, 1.0
    try:
        wer = float(jiwer.wer(reference, hypothesis))
    except (ValueError, ZeroDivisionError):
        wer = 1.0
    try:
        cer = float(jiwer.cer(reference, hypothesis))
    except (ValueError, ZeroDivisionError):
        cer = 1.0
    return round(wer, 6), round(cer, 6)


def _stt_providers(config: BenchmarkConfig, selected: list[str]) -> list[Any]:
    providers: list[Any] = []
    if "gnani" in selected:
        providers.append(GnaniSTT(config))
    if "faster-whisper" in selected:
        providers.append(FasterWhisperSTT(config, use_language_hint=True))
    if "sarvam" in selected:
        providers.append(SarvamSTT(config, "transcribe"))
    return providers


def _tts_providers(config: BenchmarkConfig, selected: list[str]) -> list[Any]:
    providers: list[Any] = []
    if "gnani" in selected:
        providers.append(GnaniTTS(config))
    if "sarvam" in selected:
        providers.append(SarvamTTS(config))
    return providers


def _stt_group(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["provider"], row["condition"], row["language"])
        groups.setdefault(key, []).append(row)
    summaries: list[dict[str, Any]] = []
    for (provider, condition, language), records in sorted(groups.items()):
        ok = [row for row in records if row["status"] == "ok"]
        wer = [float(row["wer"]) for row in ok if row.get("wer") is not None]
        cer = [float(row["cer"]) for row in ok if row.get("cer") is not None]
        latency = [
            float(row["time_to_final_ms"])
            for row in ok
            if row.get("time_to_final_ms") is not None
        ]
        rtf = [
            float(row["rtf"])
            for row in ok
            if row.get("rtf") is not None
        ]
        summaries.append(
            {
                "provider": provider,
                "condition": condition,
                "language": language,
                "count": len(records),
                "failures": len(records) - len(ok),
                "empty": sum(1 for row in ok if row.get("empty_transcript")),
                "wer_median": round(statistics.median(wer), 6) if wer else None,
                "cer_median": round(statistics.median(cer), 6) if cer else None,
                "time_to_final_median_ms": (
                    round(statistics.median(latency), 2) if latency else None
                ),
                "time_to_final_p95_ms": _percentile(latency, 95),
                "rtf_median": round(statistics.median(rtf), 6) if rtf else None,
                "rtf_p95": _percentile(rtf, 95),
            }
        )
    return summaries


def _tts_group(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["provider"], row["language"]), []).append(row)
    groups[("all", "all")] = rows
    summaries: list[dict[str, Any]] = []
    for (provider, language), records in sorted(groups.items()):
        ok = [row for row in records if row["status"] == "ok"]

        def values(key: str) -> list[float]:
            return [
                float(row[key])
                for row in ok
                if row.get(key) is not None
            ]

        first_audio = values("time_to_first_audio_ms")
        total = values("total_synthesis_ms")
        rtf = values("rtf")
        roundtrip_wer = values("roundtrip_wer")
        roundtrip_cer = values("roundtrip_cer")
        summaries.append(
            {
                "provider": provider,
                "language": language,
                "count": len(records),
                "failures": len(records) - len(ok),
                "time_to_first_audio_median_ms": (
                    round(statistics.median(first_audio), 2)
                    if first_audio
                    else None
                ),
                "time_to_first_audio_p95_ms": _percentile(first_audio, 95),
                "total_synthesis_median_ms": (
                    round(statistics.median(total), 2) if total else None
                ),
                "total_synthesis_p95_ms": _percentile(total, 95),
                "audio_duration_median_s": (
                    round(statistics.median(values("audio_duration_s")), 3)
                    if ok
                    else None
                ),
                "rtf_median": (
                    round(statistics.median(rtf), 6) if rtf else None
                ),
                "rtf_p95": _percentile(rtf, 95),
                "roundtrip_wer_median": (
                    round(statistics.median(roundtrip_wer), 6)
                    if roundtrip_wer
                    else None
                ),
                "roundtrip_cer_median": (
                    round(statistics.median(roundtrip_cer), 6)
                    if roundtrip_cer
                    else None
                ),
            }
        )
    return summaries


def _latest_raw(prefix: str) -> Path:
    paths = sorted(RESULTS_ROOT.glob(f"{prefix}-*.json"))
    if not paths:
        raise FileNotFoundError(f"No raw {prefix.upper()} benchmark file exists.")
    return paths[-1]


def _read_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"{path} has no rows array.")
    return rows


async def run_stt(
    config: BenchmarkConfig,
    *,
    runs: int,
    limit: int | None,
    conditions: list[str],
    selected: list[str],
) -> list[dict[str, Any]]:
    utterances = load_utterances()
    if limit:
        utterances = utterances[:limit]
    records: list[dict[str, Any]] = []
    providers = _stt_providers(config, selected)
    try:
        for provider in providers:
            for condition in conditions:
                wav_root = ROOT / "data" / "wav_noisy" / condition
                for utterance in utterances:
                    wav_path = wav_root / f"{utterance['id']}.wav"
                    duration_s = (
                        wav_properties(wav_path)[3] / wav_properties(wav_path)[0]
                    )
                    for run_index in range(1, runs + 1):
                        row: dict[str, Any] = {
                            "provider": provider.name,
                            "model": provider.model,
                            "mode": provider.mode,
                            "condition": condition,
                            "utterance_id": utterance["id"],
                            "language": utterance["language"],
                            "script": utterance["script"],
                            "reference": utterance["reference_text"],
                            "run": run_index,
                            "input_audio_duration_s": round(duration_s, 6),
                        }
                        try:
                            result = await provider.transcribe_file(
                                str(wav_path),
                                utterance["language"],
                            )
                            wer, cer = _score(
                                utterance["reference_text"],
                                result.text,
                            )
                            latency_s = result.t_final - result.t_request_sent
                            row.update(
                                {
                                    "status": "ok",
                                    "hypothesis": result.text,
                                    "normalized_reference": normalize_text(
                                        utterance["reference_text"]
                                    ),
                                    "normalized_hypothesis": normalize_text(
                                        result.text
                                    ),
                                    "wer": wer,
                                    "cer": cer,
                                    "empty_transcript": not bool(result.text.strip()),
                                    "time_to_final_ms": round(
                                        latency_s * 1000,
                                        3,
                                    ),
                                    "rtf": round(
                                        latency_s / duration_s,
                                        6,
                                    )
                                    if duration_s
                                    else None,
                                }
                            )
                            print(
                                f"STT {provider.name:20s} {condition:11s} "
                                f"{utterance['id']} run={run_index} "
                                f"WER={wer:.3f}"
                            )
                        except (BenchmarkProviderError, Exception) as exc:
                            row.update(
                                {
                                    "status": "error",
                                    "error": f"{type(exc).__name__}: {exc}",
                                }
                            )
                            print(
                                f"STT {provider.name:20s} {condition:11s} "
                                f"{utterance['id']} run={run_index} "
                                f"ERROR {type(exc).__name__}: {exc}"
                            )
                        records.append(row)
                        await asyncio.sleep(0.2)
    finally:
        for provider in providers:
            await provider.close()
    return records


async def _roundtrip_score(
    transcriber: FasterWhisperSTT,
    text: str,
    language: str,
    audio_bytes: bytes,
    sample_rate: int,
) -> tuple[str, float, float]:
    with tempfile.TemporaryDirectory(prefix="voxora-tts-roundtrip-") as directory:
        path = Path(directory) / "speech.wav"
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(audio_bytes)
        result = await transcriber.transcribe_file(str(path), language)
    wer, cer = _score(text, result.text)
    return result.text, wer, cer


async def run_tts(
    config: BenchmarkConfig,
    *,
    runs: int,
    limit: int | None,
    selected: list[str],
) -> list[dict[str, Any]]:
    texts: list[dict[str, str]] = json.loads(
        TTS_TEXTS_PATH.read_text(encoding="utf-8")
    )
    if limit:
        texts = texts[:limit]
    sample_rate = int(config.tts["sample_rate_hz"])
    providers = _tts_providers(config, selected)
    transcriber = FasterWhisperSTT(config, use_language_hint=True)
    records: list[dict[str, Any]] = []
    try:
        for provider in providers:
            for item in texts:
                for run_index in range(1, runs + 1):
                    row: dict[str, Any] = {
                        "provider": provider.name,
                        "model": provider.model,
                        "text_id": item["id"],
                        "language": item["language"],
                        "text": item["text"],
                        "run": run_index,
                        "sample_rate_hz": sample_rate,
                    }
                    try:
                        language = (
                            item["language"]
                            if provider.name == "gnani-timbre"
                            else {
                                "en": "en-IN",
                                "hi": "hi-IN",
                                "hinglish": "hi-IN",
                            }[item["language"]]
                        )
                        result = await provider.synthesize(
                            item["text"],
                            language,
                        )
                        audio_duration_s = len(result.audio_bytes) / (
                            sample_rate * 2
                        )
                        first_audio_ms = (
                            result.t_first_audio_byte - result.t_request_sent
                        ) * 1000
                        total_ms = (
                            result.t_done - result.t_request_sent
                        ) * 1000
                        transcript, wer, cer = await _roundtrip_score(
                            transcriber,
                            item["text"],
                            item["language"],
                            result.audio_bytes,
                            sample_rate,
                        )
                        row.update(
                            {
                                "status": "ok",
                                "audio_bytes": len(result.audio_bytes),
                                "audio_duration_s": round(audio_duration_s, 6),
                                "time_to_first_audio_ms": round(
                                    first_audio_ms,
                                    3,
                                ),
                                "total_synthesis_ms": round(total_ms, 3),
                                "rtf": round(total_ms / 1000 / audio_duration_s, 6)
                                if audio_duration_s
                                else None,
                                "roundtrip_transcript": transcript,
                                "roundtrip_wer": wer,
                                "roundtrip_cer": cer,
                            }
                        )
                        print(
                            f"TTS {provider.name:16s} {item['id']} "
                            f"run={run_index} first={first_audio_ms:.1f}ms "
                            f"WER={wer:.3f}"
                        )
                    except (BenchmarkProviderError, Exception) as exc:
                        row.update(
                            {
                                "status": "error",
                                "error": f"{type(exc).__name__}: {exc}",
                            }
                        )
                        print(
                            f"TTS {provider.name:16s} {item['id']} "
                            f"run={run_index} ERROR {type(exc).__name__}: {exc}"
                        )
                    records.append(row)
                    await asyncio.sleep(0.3)
    finally:
        for provider in providers:
            await provider.close()
        await transcriber.close()
    return records


def _markdown(
    summary: dict[str, Any],
    output_path: Path,
    summary_name: str,
) -> None:
    stt = summary.get("stt", {}).get("groups", [])
    tts = summary.get("tts", {}).get("groups", [])
    failures = summary.get("stt", {}).get("failures", []) + summary.get(
        "tts", {}
    ).get("failures", [])
    lines = [
        "# Gnani STT and TTS benchmark",
        "",
        f"Generated from `{summary_name}` and its raw run files. "
        f"Started at {summary['started_at_utc']}.",
        "",
        "## Models",
        "",
        "- Gnani STT: Prisma v2.5 over the REST transcription endpoint.",
        "- Gnani TTS: Timbre v2.5 over the realtime WebSocket endpoint.",
        "- Comparators: Sarvam Saaras v3 realtime STT, local Faster Whisper base, "
        "and Sarvam Bulbul v3.",
        "- Round-trip transcription: local Faster Whisper base for every TTS provider.",
        "",
        "## Normalization",
        "",
        summary["normalization"]["description"],
        "",
        "Limits: deterministic Devanagari transliteration is not a phonetic "
        "transcription, so spelling variants can inflate error rates. Script "
        "differences are reduced but not eliminated. English number words are "
        "used for numerals, so Hindi number wording is compared only after "
        "transliteration. The round-trip STT model frequently emitted "
        "Perso-Arabic script for Hindi speech. This normalization does not "
        "transliterate Perso-Arabic, so the Hindi round-trip scores are not "
        "interpretable as a provider-quality ranking.",
        "",
        "## STT results",
        "",
        "Every language and condition cell contains 15 utterances repeated "
        "three times. Time to final transcript starts when the provider request "
        "starts and excludes local file conversion performed before that "
        "timer. RTF divides that time by input audio duration.",
        "",
        "| Provider | Condition | Language | Runs | Failures | WER median | CER median | Final transcript median ms | p95 ms | RTF median | RTF p95 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in stt:
        lines.append(
            "| {provider} | {condition} | {language} | {count} | {failures} | "
            "{wer_median} | {cer_median} | {time_to_final_median_ms} | "
            "{time_to_final_p95_ms} | {rtf_median} | {rtf_p95} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## TTS results",
            "",
            "The intelligibility column is a round-trip STT proxy. It is not a "
            "human listening test. The same Faster Whisper base model "
            "transcribed every provider's audio.",
            "",
            "| Provider | Language | Runs | Failures | First audio median ms | p95 ms | Total synthesis median ms | p95 ms | Audio duration median s | RTF median | RTF p95 | Round-trip WER median | Round-trip CER median |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in tts:
        lines.append(
            "| {provider} | {language} | {count} | {failures} | "
            "{time_to_first_audio_median_ms} | {time_to_first_audio_p95_ms} | "
            "{total_synthesis_median_ms} | {total_synthesis_p95_ms} | "
            "{audio_duration_median_s} | {rtf_median} | {rtf_p95} | "
            "{roundtrip_wer_median} | {roundtrip_cer_median} |".format(**row)
        )
    lines.extend(["", "## Failures", ""])
    if failures:
        for row in failures:
            lines.append(
                f"- {row['provider']} / {row.get('condition', row.get('language'))} "
                f"/ {row.get('utterance_id', row.get('text_id'))}: {row['error']}"
            )
    else:
        lines.append("No failures were recorded.")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> Path:
    config = load_config()
    stamp = utc_stamp()
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "kind": "prd2-stt-tts-benchmark",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": platform.platform(),
        "network_region": config.network_region,
        "runs_per_item": args.runs,
        "normalization": {
            "description": NORMALIZATION_DESCRIPTION,
            "implementation": "bench.utils.normalize.normalize_text",
        },
        "models": {
            "gnani_stt": str(config.gnani["stt_model"]),
            "gnani_tts": str(config.gnani["tts_model"]),
            "sarvam_stt": str(config.stt["model"]),
            "faster_whisper": str(config.faster_whisper["model"]),
            "sarvam_tts": str(config.tts["model"]),
            "roundtrip_stt": f"faster-whisper-{config.faster_whisper['model']}",
        },
        "stt": {"groups": [], "failures": []},
        "tts": {"groups": [], "failures": []},
    }
    if args.reuse_stt:
        stt_path = _latest_raw("stt")
        stt_rows = _read_rows(stt_path)
        summary["stt"] = {
            "raw_results": stt_path.name,
            "groups": _stt_group(stt_rows),
            "failures": [
                row for row in stt_rows if row["status"] == "error"
            ],
        }
    elif not args.skip_stt:
        stt_path = RESULTS_ROOT / f"stt-{stamp}.json"
        stt_rows = await run_stt(
            config,
            runs=args.runs,
            limit=args.limit,
            conditions=args.conditions,
            selected=args.stt_providers,
        )
        write_json(
            stt_path,
            {
                "kind": "prd2-stt",
                "started_at_utc": summary["started_at_utc"],
                "normalization": summary["normalization"],
                "rows": stt_rows,
            },
        )
        summary["stt"] = {
            "raw_results": stt_path.name,
            "groups": _stt_group(stt_rows),
            "failures": [
                row for row in stt_rows if row["status"] == "error"
            ],
        }
    if args.reuse_tts:
        tts_path = _latest_raw("tts")
        tts_rows = _read_rows(tts_path)
        summary["tts"] = {
            "raw_results": tts_path.name,
            "groups": _tts_group(tts_rows),
            "failures": [
                row for row in tts_rows if row["status"] == "error"
            ],
        }
    elif not args.skip_tts:
        tts_path = RESULTS_ROOT / f"tts-{stamp}.json"
        tts_rows = await run_tts(
            config,
            runs=args.runs,
            limit=args.limit,
            selected=args.tts_providers,
        )
        write_json(
            tts_path,
            {
                "kind": "prd2-tts",
                "started_at_utc": summary["started_at_utc"],
                "normalization": summary["normalization"],
                "rows": tts_rows,
            },
        )
        summary["tts"] = {
            "raw_results": tts_path.name,
            "groups": _tts_group(tts_rows),
            "failures": [
                row for row in tts_rows if row["status"] == "error"
            ],
        }
    summary["finished_at_utc"] = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(),
    )
    if args.reuse_stt or args.reuse_tts:
        raw_names = [
            summary.get("stt", {}).get("raw_results"),
            summary.get("tts", {}).get("raw_results"),
        ]
        starts = []
        for name in raw_names:
            if not name:
                continue
            payload = json.loads(
                (RESULTS_ROOT / str(name)).read_text(encoding="utf-8")
            )
            started = payload.get("started_at_utc")
            if isinstance(started, str):
                starts.append(started)
        if starts:
            summary["combined_at_utc"] = summary["started_at_utc"]
            summary["started_at_utc"] = min(starts)
    summary_path = RESULTS_ROOT / f"summary-{stamp}.json"
    write_json(summary_path, summary)
    result = json.loads(summary_path.read_text(encoding="utf-8"))
    _markdown(result, RESULTS_ROOT / "REPORT.md", summary_path.name)
    print(f"Wrote {summary_path}")
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--conditions",
        nargs="+",
        choices=CONDITIONS,
        default=list(CONDITIONS),
    )
    parser.add_argument(
        "--stt-providers",
        nargs="+",
        choices=["gnani", "faster-whisper", "sarvam"],
        default=["gnani", "faster-whisper", "sarvam"],
    )
    parser.add_argument(
        "--tts-providers",
        nargs="+",
        choices=["gnani", "sarvam"],
        default=["gnani", "sarvam"],
    )
    parser.add_argument("--skip-stt", action="store_true")
    parser.add_argument("--skip-tts", action="store_true")
    parser.add_argument(
        "--reuse-stt",
        action="store_true",
        help="Reuse the latest raw STT file instead of running STT.",
    )
    parser.add_argument(
        "--reuse-tts",
        action="store_true",
        help="Reuse the latest raw TTS file instead of running TTS.",
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
