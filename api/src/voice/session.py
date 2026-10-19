"""Session state that survives across turns of one WebSocket connection."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["user", "assistant"]


@dataclass(slots=True)
class Message:
    role: Role
    content: str


@dataclass
class VoiceSession:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)
    history: list[Message] = field(default_factory=list)
    turn_count: int = 0

    def add(self, role: Role, content: str, max_messages: int = 24) -> None:
        text = content.strip()
        if not text:
            return
        self.history.append(Message(role=role, content=text))
        # Keep the window bounded but never start it with an orphan assistant
        # message after eviction.
        if len(self.history) > max_messages:
            del self.history[: len(self.history) - max_messages]
            while self.history and self.history[0].role == "assistant":
                self.history.pop(0)

    def messages_for_llm(self, system_prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            *({"role": message.role, "content": message.content} for message in self.history),
        ]


__all__ = ["Message", "VoiceSession"]
