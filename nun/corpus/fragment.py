"""Locate an Arabic fragment inside the closed Quran corpus (exact word-aligned, then fuzzy).

A simple locator used by the list builder and the labelling tool. The production candidate search (n-gram index +
GATE embeddings + reranker, SPEC §4.5) is nun.retrieval, built in M5.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from nun.corpus.store import CorpusStore
from nun.normalize.arabic import normalize_ns


@dataclass
class Word:
    sura: int
    aya: int
    simple: str
    ns: str


class QuranIndex:
    """Whole-Quran no-space string with char → word mapping, for exact fragment location."""

    def __init__(self, store: CorpusStore) -> None:
        self.words: list[Word] = []
        chars, owner = [], []
        for r in store.all():
            for w in r.text_simple.split():
                ns = normalize_ns(w)
                if not ns:
                    continue
                self.words.append(Word(r.sura, r.aya, w, ns))
                chars.append(ns)
                owner.extend([len(self.words) - 1] * len(ns))
        self.concat = "".join(chars)
        self.owner = owner
        self.word_start = {i for i, w in enumerate(owner) if i == 0 or owner[i - 1] != w}
        # per-ayah windows (1–3 consecutive ayahs within a sura) for fuzzy search
        self.ayahs = store.all()

    def find_exact(self, query_ns: str, whole_words: bool = True) -> list[tuple[int, int]]:
        """All occurrences as (first_word, last_word) index pairs."""
        hits, start = [], 0
        while (i := self.concat.find(query_ns, start)) != -1:
            j = i + len(query_ns) - 1
            end_ok = j + 1 == len(self.concat) or (j + 1) in self.word_start
            if not whole_words or (i in self.word_start and end_ok):
                hits.append((self.owner[i], self.owner[j]))
            start = i + 1
        return hits

    def span(self, w0: int, w1: int) -> dict:
        a, b = self.words[w0], self.words[w1]
        return {
            "sura": a.sura,
            "aya_from": a.aya,
            "aya_to": b.aya,
            "fragment": " ".join(w.simple for w in self.words[w0 : w1 + 1]),
            "cross_sura": a.sura != b.sura,
        }


def ref_str(sp: dict) -> str:
    return f"{sp['sura']}:{sp['aya_from']}" + (f"-{sp['aya_to']}" if sp["aya_to"] != sp["aya_from"] else "")


def quran_occurrences(idx: QuranIndex, text: str) -> list[str]:
    return sorted({ref_str(idx.span(*h)) for h in idx.find_exact(normalize_ns(text))}, key=ref_key)


def ref_key(r: str) -> tuple[int, int]:
    s, a = r.split(":")
    return int(s), int(a.split("-")[0])


def locate_fuzzy(idx: QuranIndex, q_ns: str) -> tuple[dict, float] | None:
    """Best fragment inside a 1–3-ayah window (same sura) by partial_ratio_alignment → (exact word span, score).

    The aligned character range is mapped back to corpus words, so the span covers only what matched.
    """
    grams = {q_ns[i : i + 3] for i in range(len(q_ns) - 2)}
    # char range of each ayah in idx.concat
    bounds: list[tuple[int, int, int]] = []  # (sura, char_start, char_end)
    pos = 0
    ayah_chars: dict[tuple[int, int], list[int]] = {}
    for w in idx.words:
        r = ayah_chars.setdefault((w.sura, w.aya), [pos, pos])
        pos += len(w.ns)
        r[1] = pos
    keys = list(ayah_chars)
    windows = []
    for i, (s, _a) in enumerate(keys):
        for k in (1, 2, 3):
            if i + k > len(keys) or keys[i + k - 1][0] != s:
                break
            c0, c1 = ayah_chars[keys[i]][0], ayah_chars[keys[i + k - 1]][1]
            windows.append((c0, c1, k))
    bounds = sorted(windows, key=lambda w: -sum(g in idx.concat[w[0] : w[1]] for g in grams))[:60]
    best = None
    for c0, c1, k in bounds:
        al = fuzz.partial_ratio_alignment(q_ns, idx.concat[c0:c1])
        rank = (round(al.score, 1), -k)  # higher score first, then the smallest window
        if best is None or rank > best[0]:
            best = (rank, c0 + al.dest_start, c0 + al.dest_end - 1, al.score)
    if not best:
        return None
    _, g0, g1, score = best
    return idx.span(idx.owner[g0], idx.owner[g1]), score
