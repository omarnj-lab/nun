"""«بينات: أسئلة وأجوبة عن الإسلام» (Osoul Center, 2024): the package-designated source for general questions and
misconceptions (RULES.md §3.5, SOURCES.md §3). One document per question, retrieved by an Arabic search query.

The PDF is fetched at build time into data/raw/bayyinat/ (git-ignored; redistribution terms unconfirmed) and indexed
here in memory. Its text layer stores lam-alef ligatures in reverse order; `fix()` repairs the frequent cases
(الله, the article before a hamza) and leaves the rest, which models read without trouble.

    python -m nun.chat.bayyinat --fetch      # download the PDF (once)
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from nun.normalize.arabic import normalize

PDF_URL = "https://dawa.center/storage/files/AMYj6DfmHlSnZ766Zz0VlBNwmYtdwhAl31XMETlT.pdf"
PAGE_URL = "https://dawa.center/file/7937"
PDF_PATH = Path("data/raw/bayyinat/bayyinat.pdf")
TITLE = "بينات: أسئلة وأجوبة عن الإسلام (مركز أصول، 1445هـ)"
MIN_SCORE = 4.0  # BM25 score below which no question is considered relevant

_FIXES = [
    ("هللا", "الله"),  # heading form of اللهِ
    ("اهلل", "الله"),
    ("هلل", "لله"),
    ("األ", "الأ"),
    ("اإل", "الإ"),
    ("اآل", "الآ"),
]


def fix(text: str) -> str:
    for a, b in _FIXES:
        text = text.replace(a, b)
    return text


@dataclass
class Entry:
    n: int  # question number in the book (1-based, in order)
    page: int  # 1-based PDF page where the question starts
    question: str
    similar: str
    short: str  # «مختصر الإجابة»
    body: str  # the full answer (trimmed)


def _between(text: str, start: str, ends: list[str]) -> str:
    i = text.find(start)
    if i < 0:
        return ""
    i += len(start)
    j = min([k for k in (text.find(e, i) for e in ends) if k >= 0] or [len(text)])
    return text[i:j].strip()


def _clean(text: str) -> str:
    text = re.sub(r"\n\s*3\s*\n", "\n• ", text)  # bullet glyphs come out as "3"
    text = re.sub(r"\d+ أسئلة منتقاة حول الإسلام- بينات", " ", text)  # running page header
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{2,}", "\n", text)).strip()


def parse(pdf: Path = PDF_PATH) -> list[Entry]:
    import pymupdf

    doc = pymupdf.open(pdf)
    pages = [fix(p.get_text()) for p in doc]
    starts = [i for i in range(20, len(pages)) if "السؤال" in (ln.strip() for ln in pages[i].split("\n"))]
    out = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(pages)
        text = _clean("\n".join(pages[s:e]))
        q = _between(text, "السؤال\n", ["عبارات مشابهة للسؤال", "الجواب\n"])
        similar = _between(text, "عبارات مشابهة للسؤال", ["الجواب\n"])
        short = _between(text, "مختصَرُ الإجابة", ["الجوابُ التفصيلي", "الجواب التفصيلي"])
        body = text[text.find("الجواب\n") :] if "الجواب\n" in text else text
        out.append(Entry(k + 1, s + 1, q.strip(" :\n"), similar.strip(" :\n•"), short.strip(" :\n"), body[:7000]))
    return out


_TOKEN = re.compile(r"\S+")
_STOP = set(normalize("في من على عن الى ان او ما هل لا لم لماذا كيف هذا هذه ذلك التي الذي و ثم مع كل اي هو هي").split())


def _tokens(text: str) -> list[str]:
    out = []
    for w in _TOKEN.findall(normalize(text)):
        if w in _STOP or len(w) < 2:
            continue
        out.append(w[2:] if w.startswith("ال") and len(w) > 4 else w)  # drop the article
    return out


class Index:
    """BM25 over question + similar phrasings (weighted ×3) + short answer."""

    def __init__(self, entries: list[Entry]) -> None:
        self.entries = entries
        self.docs = [_tokens(" ".join([e.question] * 3 + [e.similar] * 3 + [e.short])) for e in entries]
        self.avg = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def search(self, query: str, k: int = 3) -> list[tuple[Entry, float]]:
        q = _tokens(query)
        scores = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * dl / self.avg))
            scores.append((s, i))
        scores.sort(reverse=True)
        return [(self.entries[i], s) for s, i in scores[:k] if s >= MIN_SCORE]


@lru_cache
def index() -> Index | None:
    if not PDF_PATH.exists():
        return None
    return Index(parse())


def fetch() -> None:
    import urllib.request

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(PDF_URL, headers={"User-Agent": "NunHackathon/0.3"})
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 — fixed https URL
        PDF_PATH.write_bytes(r.read())


if __name__ == "__main__":
    import sys

    if "--fetch" in sys.argv:
        fetch()
    idx = index()
    print(len(idx.entries) if idx else "no PDF", "questions")
    for q in sys.argv[1:]:
        if q.startswith("--"):
            continue
        for e, s in idx.search(q):
            print(f"{s:5.1f}  #{e.n} p{e.page}  {e.question[:90]}")
