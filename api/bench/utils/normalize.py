"""Script-aware text normalization for identical STT reference/hypothesis scoring.

Devanagari is deterministically transliterated to Latin, using the mapping below,
before WER/CER is calculated. The same function is applied to every reference and
hypothesis, so a provider returning Devanagari, Roman, or mixed script lands in a
single comparison space without a second model call.
"""

from __future__ import annotations

import re
import unicodedata

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

_INDEPENDENT_VOWELS = {
    "अ": "a",
    "आ": "aa",
    "इ": "i",
    "ई": "ii",
    "उ": "u",
    "ऊ": "uu",
    "ऋ": "ri",
    "ॠ": "rii",
    "ऌ": "li",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
    "ऑ": "o",
}

_CONSONANTS = {
    "क": "k",
    "ख": "kh",
    "ग": "g",
    "घ": "gh",
    "ङ": "ng",
    "च": "ch",
    "छ": "chh",
    "ज": "j",
    "झ": "jh",
    "ञ": "ny",
    "ट": "t",
    "ठ": "th",
    "ड": "d",
    "ढ": "dh",
    "ण": "n",
    "त": "t",
    "थ": "th",
    "द": "d",
    "ध": "dh",
    "न": "n",
    "प": "p",
    "फ": "ph",
    "ब": "b",
    "भ": "bh",
    "म": "m",
    "य": "y",
    "र": "r",
    "ल": "l",
    "व": "v",
    "श": "sh",
    "ष": "sh",
    "स": "s",
    "ह": "h",
    "ळ": "l",
    "क़": "q",
    "ख़": "kh",
    "ग़": "g",
    "ज़": "z",
    "ड़": "r",
    "ढ़": "rh",
    "फ़": "f",
    "य़": "y",
}

_MATRAS = {
    "ा": "aa",
    "ि": "i",
    "ी": "ii",
    "ु": "u",
    "ू": "uu",
    "ृ": "ri",
    "ॄ": "rii",
    "ॢ": "li",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
    "ॉ": "o",
    "ॅ": "ae",
    "ॆ": "e",
    "ॊ": "o",
}

_MARKS = {
    "ं": "n",
    "ँ": "n",
    "ः": "h",
    "ऽ": "",
    "्": "",
    "़": "",
}

_ONES = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TENS = (
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
)
_SCALES = (
    (10**9, "billion"),
    (10**6, "million"),
    (1000, "thousand"),
    (100, "hundred"),
)


def _under_1000(value: int) -> str:
    words: list[str] = []
    for scale, name in ((100, "hundred"),):
        if value >= scale:
            count, value = divmod(value, scale)
            words.extend([_ONES[count], name])
    if value >= 20:
        tens, value = divmod(value, 10)
        words.append(_TENS[tens])
    if value:
        words.append(_ONES[value])
    return " ".join(words)


def number_to_words(value: int) -> str:
    if value < 0:
        return "minus " + number_to_words(-value)
    if value < 20:
        return _ONES[value]
    words: list[str] = []
    remaining = value
    for scale, name in _SCALES:
        if remaining >= scale:
            count, remaining = divmod(remaining, scale)
            words.extend([_under_1000(count), name])
    if remaining:
        words.append(_under_1000(remaining))
    return " ".join(part for part in words if part)


def transliterate_devanagari(text: str) -> str:
    output: list[str] = []
    chars = list(text)
    index = 0
    while index < len(chars):
        char = chars[index]
        combined = char + chars[index + 1] if index + 1 < len(chars) else char
        if combined in _CONSONANTS:
            output.append(_CONSONANTS[combined])
            index += 2
            if index < len(chars) and chars[index] in _MARKS:
                mark = chars[index]
                output.append(_MARKS[mark])
                index += 1
            elif index >= len(chars) or (
                chars[index] not in _MATRAS and chars[index] != "्"
            ):
                output.append("a")
            continue
        if char in _CONSONANTS:
            output.append(_CONSONANTS[char])
            index += 1
            if index < len(chars) and chars[index] in _MARKS:
                output.append(_MARKS[chars[index]])
                index += 1
            elif index >= len(chars) or (
                chars[index] not in _MATRAS and chars[index] != "्"
            ):
                output.append("a")
            continue
        if char in _INDEPENDENT_VOWELS:
            output.append(_INDEPENDENT_VOWELS[char])
        elif char in _MATRAS:
            output.append(_MATRAS[char])
        elif char in _MARKS:
            output.append(_MARKS[char])
        else:
            output.append(char)
        index += 1
    return "".join(output)


def normalize_text(text: str) -> str:
    """Return lowercase, punctuation-free, Latin-script scoring text."""
    value = unicodedata.normalize("NFC", text or "")
    value = value.translate(DEVANAGARI_DIGITS)

    def replace_number(match: re.Match[str]) -> str:
        try:
            return f" {number_to_words(int(match.group(0)))} "
        except ValueError:
            return match.group(0)

    value = re.sub(
        r"(?<!\w)(?:\d{1,3}(?:,\d{3})+|\d+)(?!\w)",
        replace_number,
        value,
    )
    value = transliterate_devanagari(value)
    value = value.lower().replace("।", " ")
    value = "".join(
        " " if unicodedata.category(char).startswith(("P", "S")) else char
        for char in value
    )
    value = re.sub(r"\s+", " ", value).strip()
    return value


def detect_script(text: str) -> str:
    """Classify a transcript as Devanagari, Latin, mixed, or empty."""
    letters = [char for char in text or "" if char.isalpha()]
    if not letters:
        return "empty"
    devanagari = sum(1 for char in letters if "\u0900" <= char <= "\u097F")
    latin = sum(1 for char in letters if "a" <= char.lower() <= "z")
    total = len(letters)
    if devanagari / total >= 0.20 and latin / total >= 0.20:
        return "mixed"
    if devanagari / total >= 0.20:
        return "devanagari"
    if latin / total >= 0.20:
        return "latin"
    return "other"


def parse_entities(value: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    for item in (value or "").split(";"):
        if not item.strip() or "=" not in item:
            continue
        entity_type, entity_value = item.split("=", 1)
        entities.append(
            {
                "type": entity_type.strip(),
                "value": entity_value.strip(),
            }
        )
    return entities


__all__ = [
    "detect_script",
    "normalize_text",
    "number_to_words",
    "parse_entities",
    "transliterate_devanagari",
]
