"""Arabic normalisation for MATCHING only (SPEC §3.3). Never apply to display text.

Applied identically to corpus text (Tanzil simple-clean) and to model readings.
"""

from __future__ import annotations

import re
import unicodedata

UNREADABLE = "[؟]"

TATWEEL = "ـ"
# harakat, Quranic annotation marks, dagger alef, extended-Arabic open tanween
_MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ࣓-ࣿ]")
_FOLD = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
        "ء": None,
        # Persian/Urdu letter forms models sometimes emit
        "ی": "ي",
        "ې": "ي",
        "ک": "ك",
        "ە": "ه",
        "ہ": "ه",
        "ۃ": "ه",
        "ھ": "ه",
    }
)
# after folding, keep only the 28 base letters (+ ه/و/ي already covered) and spaces
_NON_LETTER = re.compile("[^ا-غف-ي ]+")
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Normalise Arabic text for matching: strip marks, fold letter variants, keep letters and single spaces."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace(TATWEEL, "")
    text = _MARKS.sub("", text)
    text = text.translate(_FOLD)
    text = _NON_LETTER.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def normalize_ns(text: str) -> str:
    """normalize() without spaces (calligraphy often merges or splits words)."""
    return normalize(text).replace(" ", "")


def split_segments(reading: str) -> list[str]:
    """Split a model reading on [؟] markers and newlines into normalised, non-empty segments."""
    parts = re.split(r"\[\s*؟\s*\]|\n", reading)
    return [n for n in (normalize(p) for p in parts) if n]
