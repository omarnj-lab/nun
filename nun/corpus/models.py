"""Corpus record models (SPEC §3.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TranslationText(BaseModel):
    lang: str
    text: str
    footnotes: str | None = None
    version: str | None = None


class QuranRecord(BaseModel):
    id: str
    type: Literal["quran"] = "quran"
    sura: int
    aya: int
    text_uthmani: str  # verbatim QuranEnc arabic_text; DISPLAY ONLY
    text_simple: str  # Tanzil simple-clean; MATCHING ONLY
    text_norm: str
    text_norm_ns: str
    sura_name_ar: str
    sura_name_en: str
    sura_name_en_meaning: str
    juz: int
    revelation: Literal["meccan", "medinan"]
    translations: dict[str, TranslationText]  # keyed by QuranEnc key; approval status in nun.corpus.sources
    tafsir: dict[str, TranslationText]
    audio: dict[str, str]
