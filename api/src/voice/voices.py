"""Sarvam voice catalog exposed to the browser.

Sarvam keeps the authoritative speaker list in its API reference. We keep a
small, typed copy here so the voice picker can be populated without an extra
round trip to Sarvam on every page load.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Gender = Literal["female", "male"]


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    gender: Gender
    description: str

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "description": self.description,
        }


def _voice(voice_id: str, gender: Gender, description: str) -> Voice:
    return Voice(
        id=voice_id,
        name=voice_id.replace("_", " ").title(),
        gender=gender,
        description=description,
    )


# Sarvam Bulbul v3 speakers. Source: Sarvam API reference (speaker enum).
V3_VOICES: tuple[Voice, ...] = (
    _voice("shubh", "male", "Warm and versatile"),
    _voice("aditya", "male", "Clear and composed"),
    _voice("ritu", "female", "Expressive and friendly"),
    _voice("priya", "female", "Bright and approachable"),
    _voice("neha", "female", "Conversational and warm"),
    _voice("rahul", "male", "Confident and clear"),
    _voice("pooja", "female", "Friendly and expressive"),
    _voice("rohan", "male", "Calm and reassuring"),
    _voice("simran", "female", "Natural and engaging"),
    _voice("kavya", "female", "Energetic and bright"),
    _voice("amit", "male", "Steady and trustworthy"),
    _voice("dev", "male", "Deep and composed"),
    _voice("ishita", "female", "Clear and helpful"),
    _voice("shreya", "female", "Warm and polished"),
    _voice("ratan", "male", "Rich and expressive"),
    _voice("varun", "male", "Confident and dynamic"),
    _voice("manan", "male", "Friendly and relaxed"),
    _voice("sumit", "male", "Practical and clear"),
    _voice("roopa", "female", "Gentle and expressive"),
    _voice("kabir", "male", "Warm and conversational"),
    _voice("aayan", "male", "Young and lively"),
    _voice("ashutosh", "male", "Thoughtful and measured"),
    _voice("advait", "male", "Calm and articulate"),
    _voice("anand", "male", "Warm and reassuring"),
    _voice("tanya", "female", "Bright and conversational"),
    _voice("tarun", "male", "Energetic and clear"),
    _voice("sunny", "male", "Upbeat and friendly"),
    _voice("mani", "male", "Smooth and expressive"),
    _voice("gokul", "male", "Clear and grounded"),
    _voice("vijay", "male", "Confident and warm"),
    _voice("shruti", "female", "Soft and clear"),
    _voice("suhani", "female", "Lively and expressive"),
    _voice("mohit", "male", "Friendly and casual"),
    _voice("kavitha", "female", "Warm and articulate"),
    _voice("rehan", "male", "Young and conversational"),
    _voice("soham", "male", "Calm and thoughtful"),
    _voice("rupali", "female", "Bright and engaging"),
)

V2_VOICES: tuple[Voice, ...] = (
    _voice("anushka", "female", "Warm and expressive"),
    _voice("manisha", "female", "Clear and confident"),
    _voice("vidya", "female", "Calm and articulate"),
    _voice("arya", "female", "Bright and friendly"),
    _voice("abhilash", "male", "Rich and conversational"),
    _voice("karun", "male", "Smooth and composed"),
    _voice("hitesh", "male", "Warm and clear"),
)

# Bulbul v4-flash uses persona IDs rather than the short v2/v3 names. This is a
# useful subset of the English/Hindi conversational personas; callers can still
# use any persona ID from Sarvam's catalog through TTS_VOICE.
V4_VOICES: tuple[Voice, ...] = tuple(
    _voice(voice_id, gender, description)
    for voice_id, gender, description in (
        ("shubh_en_narration", "male", "Warm English narrator"),
        ("shubh_en_narration_gentle", "male", "Gentle English narrator"),
        ("shubh_en_audiobook", "male", "English audiobook voice"),
        ("shubh_en_ads", "male", "Energetic English ads"),
        ("shubh_en_recovery", "male", "Calm English support"),
        ("shubh_en_sports", "male", "Excited English sports"),
        ("simran_en_conversation", "female", "Natural English conversation"),
        ("simran_en_customer", "female", "Helpful English support"),
        ("simran_en_edtech", "female", "Clear English teaching"),
        ("simran_en_sales", "female", "Confident English sales"),
        ("simran_en_therapist", "female", "Calm English therapy"),
        ("ishita_en_customer", "female", "Friendly English support"),
        ("ishita_en_medical", "female", "Clear English medical"),
        ("ishita_en_social", "female", "Lively English social"),
        ("ishita_en_stories", "female", "Expressive English stories"),
        ("neha_en_customer", "female", "Warm English support"),
        ("neha_en_latenight", "female", "Relaxed English late night"),
        ("ritu_en_edtech", "female", "Bright English teaching"),
        ("ritu_en_medical", "female", "Clear English medical"),
        ("ritu_en_reels", "female", "Energetic English reels"),
        ("rohan_en_recovery", "male", "Calm English support"),
        ("dev_en_conversational", "male", "Natural English conversation"),
        ("varun_en_ads", "male", "Bold English ads"),
        ("sanchita_en_companion", "female", "Warm English companion"),
        ("shalini_en_companion", "female", "Friendly English companion"),
        ("aparna_en_companion", "female", "Gentle English companion"),
        ("aditi_en_stories", "female", "Playful English stories"),
        ("roopa_en_conversational", "female", "Natural English conversation"),
        ("shubh_enhi_companion", "male", "Warm English-Hindi companion"),
        ("simran_enhi_companion", "female", "Warm English-Hindi companion"),
        ("ishita_enhi_customer", "female", "Helpful English-Hindi support"),
        ("pooja_hi_conversational", "female", "Natural Hindi conversation"),
        ("aditya_hi_conversational", "male", "Natural Hindi conversation"),
        ("ritu_hi_conversation", "female", "Friendly Hindi conversation"),
        ("shreya_hi_conversational", "female", "Warm Hindi conversation"),
        ("simran_hi_conversation", "female", "Natural Hindi conversation"),
        ("kavya_hi_conversational", "female", "Bright Hindi conversation"),
        ("aayan_hi_conversational", "male", "Young Hindi conversation"),
    )
)

SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "bn-IN",
    "en-IN",
    "gu-IN",
    "hi-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "od-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
)


def voices_for_model(model: str) -> tuple[Voice, ...]:
    """Return the speakers that belong to the configured Bulbul version."""
    version = model.lower()
    if "bulbul:v2" in version:
        return V2_VOICES
    if "bulbul:v4" in version:
        return V4_VOICES
    return V3_VOICES


def build_catalog(model: str, default_voice: str) -> dict[str, object]:
    voices = voices_for_model(model)
    known = {voice.id for voice in voices}
    selected = default_voice if default_voice in known else voices[0].id
    return {
        "provider": "sarvam",
        "kind": "audio",
        "model": model,
        "default_voice": selected,
        "languages": list(SUPPORTED_LANGUAGES),
        "voices": [voice.as_dict() for voice in voices],
        "cache_ttl_seconds": 86_400,
    }


__all__ = [
    "Gender",
    "Voice",
    "V2_VOICES",
    "V3_VOICES",
    "V4_VOICES",
    "SUPPORTED_LANGUAGES",
    "build_catalog",
    "voices_for_model",
]
