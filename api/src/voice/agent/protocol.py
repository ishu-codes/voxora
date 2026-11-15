"""Structured model actions used by the Demo Bank agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDecision:
    action: str
    tool: str | None
    name: str | None
    notice: str | None
    text: str | None


def parse_agent_decision(raw: str) -> AgentDecision:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("The model did not return a JSON action.") from exc
    if not isinstance(payload, dict):
        raise ValueError("The model action must be an object.")
    action = str(payload.get("action", "")).strip().lower()
    if action not in {"tool", "answer"}:
        raise ValueError(f"Unsupported agent action {action!r}.")
    tool = payload.get("tool")
    name = payload.get("name")
    notice = payload.get("notice")
    answer = payload.get("text")
    if action == "tool" and tool not in {"list_docs", "read_doc"}:
        raise ValueError(f"Unsupported document tool {tool!r}.")
    if action == "tool" and tool == "read_doc" and not isinstance(name, str):
        raise ValueError("read_doc requires a document name.")
    return AgentDecision(
        action=action,
        tool=str(tool) if isinstance(tool, str) else None,
        name=str(name) if isinstance(name, str) else None,
        notice=str(notice).strip() if isinstance(notice, str) else None,
        text=str(answer).strip() if isinstance(answer, str) else None,
    )


__all__ = ["AgentDecision", "parse_agent_decision"]
