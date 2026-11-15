"""Run the Demo Bank question set against the real LLM and document tools."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, AsyncIterator

from src.voice.agent.documents import BANK_DOCS_DIR
from src.voice.core.config import SAMPLE_RATE, Settings
from src.voice.providers.llm import build_llm
from src.voice.runtime.pipeline import VoicePipeline
from src.voice.runtime.session import VoiceSession
from src.voice.runtime.transport import CollectingTransport
from src.voice.scenarios import get_scenario

QUESTIONS_PATH = BANK_DOCS_DIR.parent / "demo_bank_questions.json"


class SilentSTT:
    name = "evaluation-warmup"
    supports_partials = False

    async def begin_utterance(self, on_partial=None) -> None:
        return None

    async def push_audio(self, pcm: bytes) -> None:
        return None

    async def end_utterance(self) -> str:
        return ""

    async def cancel_utterance(self) -> None:
        return None

    async def close(self) -> None:
        return None


class SilentTTS:
    name = "evaluation-silent-tts"
    kind = "audio"
    sample_rate = SAMPLE_RATE

    async def prepare(self, voice: str | None = None) -> None:
        return None

    async def _stream(
        self,
        text: str,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        yield b"\x00\x00" * 160

    def synthesize(
        self,
        text: str,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        return self._stream(text, voice)

    async def close(self) -> None:
        return None


def _contains_any(text: str, groups: list[list[str]]) -> bool:
    lower = text.lower()
    return all(any(phrase.lower() in lower for phrase in group) for group in groups)


async def run_case(
    case: dict[str, Any],
    settings: Settings,
    llm: Any,
) -> dict[str, Any]:
    transport = CollectingTransport()
    pipeline = VoicePipeline(
        transport,
        replace(settings, system_prompt=get_scenario("demo-bank").system_prompt),
        SilentSTT(),
        llm,
        SilentTTS(),
        session=VoiceSession(),
        scenario_id="demo-bank",
    )
    pipeline._generation = 1
    pipeline._turns[1] = {
        "turn_id": pipeline._label(1),
        "speech_duration_ms": 0,
        "stt": "evaluation",
        "llm": llm.name,
        "tts": "evaluation",
    }
    error: str | None = None
    try:
        await pipeline._run_bank_assistant(1, case["question"], time.monotonic())
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    done = transport.of_type("assistant.done")
    transcript = str(done[-1]["text"]) if done else ""
    tools = transport.of_type("bank.tool.call")
    docs = [
        document
        for event in transport.of_type("bank.documents.used")
        for document in event.get("documents", [])
    ]
    expected_docs = list(case.get("expected_docs", []))
    forbidden = [
        phrase
        for phrase in case.get("forbidden", [])
        if phrase.lower() in transcript.lower()
    ]
    checks = {
        "completed": not error and bool(transcript),
        "documents": all(name in docs for name in expected_docs),
        "behavior": _contains_any(
            transcript,
            case.get("required_any", []),
        ),
        "forbidden": not forbidden,
        "tool_limit": len(tools) <= 3,
        "notice": not tools or bool(transport.of_type("bank.notice")),
    }
    return {
        "id": case["id"],
        "language": case["language"],
        "question": case["question"],
        "expected_behavior": case["expected_behavior"],
        "transcript": transcript,
        "tools": [
            {
                "tool": event["tool"],
                "arguments": event.get("arguments", {}),
            }
            for event in tools
        ],
        "documents": docs,
        "checks": checks,
        "forbidden_found": forbidden,
        "error": error,
        "pass": all(checks.values()),
    }


async def main() -> None:
    cases = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    settings = Settings.from_env()
    llm, reason = build_llm(settings)
    results = []
    try:
        for case in cases:
            result = await run_case(case, settings, llm)
            results.append(result)
            print(
                f"\n[{'PASS' if result['pass'] else 'FAIL'}] "
                f"{result['id']} ({result['language']})"
            )
            print(f"Q: {result['question']}")
            print(f"A: {result['transcript'] or result['error']}")
            print(f"Tools: {result['tools']}")
            if not result["pass"]:
                print(f"Checks: {result['checks']}")
    finally:
        await llm.close()

    passed = sum(1 for result in results if result["pass"])
    payload = {
        "kind": "demo-bank-agent-evaluation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "llm": llm.name,
        "llm_reason": reason,
        "passed": passed,
        "total": len(results),
        "results": results,
    }
    output = BANK_DOCS_DIR.parent / "demo_bank_results.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n{passed}/{len(results)} passed")
    print(f"Wrote {output}")


if __name__ == "__main__":
    asyncio.run(main())
