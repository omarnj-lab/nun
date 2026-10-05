"""Nearest-ayah search for a model's reading (the reading path): which place in the Quran does this text match?

Units are single ayahs and 2- and 3-ayah windows of the corpus text, in two orthographic variants (dagger alef read
as alef, or dropped), normalised for matching only. Candidates come from a character-3-gram index, then rapidfuzz
scores them. Same method as analysis/v1_verse_id (where it was measured), on the app's own corpus.
The text shown to visitors is always the corpus text of the returned reference, never the reading.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz

from nun.corpus.store import CorpusStore

_MARKS = re.compile("[ؐ-ًؚ-ٟۖ-ۭـ]")  # harakat, Quranic marks, tatweel


def norm(text: str, dagger: str = "map") -> str:
    t = unicodedata.normalize("NFKC", str(text))
    t = t.replace("ٰ", "ا" if dagger == "map" else "")  # dagger alef
    t = _MARKS.sub("", t)
    t = re.sub("[إأآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    t = re.sub("[^ء-ي ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _ns(t: str) -> str:
    return t.replace(" ", "")


def _grams(t: str) -> set[str]:
    return {t[i : i + 3] for i in range(max(0, len(t) - 2))}


@dataclass
class Hit:
    score: float  # rapidfuzz 0-100
    sura: int
    aya_from: int
    aya_to: int
    qlen: int  # letters in the reading segment
    basmala: bool

    @property
    def ref(self) -> str:
        return f"{self.sura}:{self.aya_from}" + (f"-{self.aya_to}" if self.aya_to != self.aya_from else "")

    def overlaps(self, other: Hit, slack: int = 2) -> bool:
        return (
            self.sura == other.sura and self.aya_from <= other.aya_to + slack and other.aya_from <= self.aya_to + slack
        )


class VerseSearch:
    def __init__(self, store: CorpusStore) -> None:
        by_sura: dict[int, list] = defaultdict(list)
        for r in store.all():
            by_sura[r.sura].append((r.aya, r.text_uthmani))
        self.units: list[tuple[int, int, int, str]] = []  # sura, aya_from, aya_to, normalised text (no spaces)
        for s, ayas in by_sura.items():
            for i in range(len(ayas)):
                for w in (1, 2, 3):
                    if i + w > len(ayas):
                        break
                    chunk = ayas[i : i + w]
                    for var in ("map", "drop"):
                        self.units.append((s, chunk[0][0], chunk[-1][0], _ns(" ".join(norm(t, var) for _, t in chunk))))
        self.index: dict[str, list[int]] = defaultdict(list)
        for ui, u in enumerate(self.units):
            for g in _grams(u[3]):
                self.index[g].append(ui)
        self.basmala = _ns(norm("بسم الله الرحمن الرحيم", "drop"))

    def locate(self, segment: str) -> Hit | None:
        q = _ns(norm(segment, "map"))
        if len(q) < 4:
            return None
        votes: dict[int, int] = defaultdict(int)
        for g in _grams(q):
            for ui in self.index.get(g, ()):
                votes[ui] += 1
        best = None
        for ui in sorted(votes, key=votes.get, reverse=True)[:200]:
            s, a, b, t = self.units[ui]
            sc = fuzz.partial_ratio(q, t) if len(q) <= len(t) else fuzz.ratio(q, t)
            key = (sc, -len(t))  # tightest unit at equal score
            if best is None or key > best[0]:
                best = (key, ui)
        if best is None:
            return None
        (sc, _), ui = best
        s, a, b, _t = self.units[ui]
        is_basmala = fuzz.ratio(q, self.basmala) >= 85 and len(q) <= len(self.basmala) * 1.3
        return Hit(sc, s, a, b, len(q), is_basmala)

    def read(self, segments: list[str]) -> tuple[Hit | None, list[Hit]]:
        """Best located segment (longest strong non-Basmala line) and every located line."""
        hits = [h for h in (self.locate(s) for s in segments if s.strip()) if h]
        pool = [h for h in hits if not h.basmala] or hits
        if not pool:
            return None, []
        return max(pool, key=lambda h: (h.qlen * h.score / 100, h.score)), hits


@lru_cache
def searcher() -> VerseSearch:
    return VerseSearch(CorpusStore())
