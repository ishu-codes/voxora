"""Turn a token stream into speakable phrases.

TTS providers sound much better when they receive a full clause or sentence
instead of a single token.  The chunker also caps the buffer so a model that
refuses to punctuate cannot stall synthesis.
"""

from __future__ import annotations

import re

_BOUNDARY = re.compile(r"(?<=[.!?;:])\s+|\n+")
_ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "sr.",
    "jr.",
    "st.",
    "vs.",
    "e.g.",
    "i.e.",
}


class SentenceChunker:
    def __init__(self, min_chars: int = 24, max_chars: int = 220) -> None:
        self.min_chars = min_chars
        self.max_chars = max_chars
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        if not text:
            return []
        self._buffer += text
        chunks: list[str] = []

        while True:
            candidate = self._next_chunk()
            if candidate is None:
                break
            chunks.append(candidate)

        return chunks

    def _next_chunk(self) -> str | None:
        buffer = self._buffer
        if len(buffer) < self.min_chars:
            return None

        for match in _BOUNDARY.finditer(buffer):
            end = match.start()
            piece = buffer[:end].strip()
            if len(piece) < self.min_chars:
                continue
            if piece.lower().endswith(tuple(_ABBREVIATIONS)):
                continue
            self._buffer = buffer[match.end() :].lstrip()
            return piece

        if len(buffer) > self.max_chars:
            split_at = buffer.rfind(" ", 0, self.max_chars)
            if split_at < self.min_chars:
                split_at = self.max_chars
            piece = buffer[:split_at].strip()
            self._buffer = buffer[split_at:].lstrip()
            return piece or None
        return None

    def flush(self) -> str | None:
        piece = self._buffer.strip()
        self._buffer = ""
        return piece or None


__all__ = ["SentenceChunker"]
