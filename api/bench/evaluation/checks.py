"""Deterministic, model-independent checks applied to every agent turn."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

from bench.utils.normalize import normalize_text

_MARKDOWN = re.compile(r"[*#`]|^\s*-\s", re.MULTILINE)
_EMOJI = re.compile(
    "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF]"
)
@dataclass
class CheckResult:
    check: str
    status: str
    detail: str = ""
    probability: float | None = None
    question_polarity: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _leaks_prompt(reply: str, prompt: str, window: int = 8) -> str | None:
    reply_words = normalize_text(reply).split()
    prompt_text = normalize_text(prompt)
    for index in range(max(0, len(reply_words) - window + 1)):
        fragment = " ".join(reply_words[index : index + window])
        if fragment and fragment in prompt_text:
            return fragment
    return None


def check_turn(
    reply: str,
    user_text: str,
    active_prompt: str,
    fallback_language: str,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    words = reply.split()
    results.append(
        CheckResult(
            "word_count",
            "pass" if len(words) <= 40 else "fail",
            f"{len(words)} words",
        )
    )
    markup = _MARKDOWN.search(reply)
    results.append(
        CheckResult(
            "no_markdown",
            "fail" if markup else "pass",
            f"found {markup.group(0)!r}" if markup else "",
        )
    )
    emoji = _EMOJI.search(reply)
    results.append(
        CheckResult(
            "no_emoji",
            "fail" if emoji else "pass",
            f"found {emoji.group(0)!r}" if emoji else "",
        )
    )
    digits = [char for char in reply if unicodedata.category(char) == "Nd"]
    results.append(
        CheckResult(
            "no_digits",
            "fail" if digits else "pass",
            f"found {' '.join(digits)}" if digits else "",
        )
    )

    leak = _leaks_prompt(reply, active_prompt)
    results.append(
        CheckResult(
            "prompt_overlap_informational",
            "info",
            f"matched prompt fragment: {leak}" if leak else "",
        )
    )
    results.append(
        CheckResult(
            "expected_language_fallback",
            "info",
            fallback_language,
        )
    )
    return results


def turn_passes(results: list[CheckResult]) -> bool:
    return all(result.status != "fail" for result in results)


__all__ = [
    "CheckResult",
    "check_turn",
    "turn_passes",
]
