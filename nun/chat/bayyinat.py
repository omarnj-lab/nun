"""«بينات: أسئلة وأجوبة عن الإسلام» (Osoul Center, 2024): the package-designated source for general questions and
misconceptions (RULES.md §3.5, SOURCES.md §3). One document per question, retrieved by an Arabic search query.

The PDF is fetched at build time into data/raw/bayyinat/ (git-ignored; redistribution terms unconfirmed), parsed
once with pypdf (BSD) into bayyinat.json next to it, and indexed in memory. pypdf keeps the body text intact; the
decorative headings come out garbled, so they are matched by their first letters.

    python -m nun.chat.bayyinat --fetch      # download the PDF (once)
"""

from __future__ import annotations

import json
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
JSON_PATH = PDF_PATH.with_suffix(".json")
TITLE = "بينات: أسئلة وأجوبة عن الإسلام (مركز أصول، 1445هـ)"
MIN_SCORE = 4.0  # BM25 score below which no question is considered relevant


@dataclass
class Entry:
    n: int  # question number in the book (1-based, in order)
    page: int  # 1-based PDF page where the question starts
    question: str
    similar: str
    short: str  # «مختصر الإجابة»
    body: str  # the full answer (trimmed)


SIMILAR = re.compile(r"^عبارات مشا")
ANSWER = re.compile(r"^الجواب\s*$")
SHORT = re.compile(r"^مختص")
DETAIL = re.compile(r"التفصيل")


def _clean(text: str) -> str:
    text = re.sub(r"^\s*\d+\s*$|^بينات - أسئلة منتقاة حول الإسلام\s*$", "", text, flags=re.M)  # page furniture
    text = text.replace("\t", "• ")
    return re.sub(r"[ ]+", " ", re.sub(r"\n{2,}", "\n", text)).strip()


def _split(lines: list[str]) -> tuple[str, str, str, str]:
    """question, similar phrasings, short answer, full answer from one question's lines."""

    def find(rx: re.Pattern, start: int = 0) -> int:
        return next((i for i in range(start, len(lines)) if rx.search(lines[i].strip())), -1)

    q0 = next(i for i, ln in enumerate(lines) if ln.strip() == "السؤال") + 1
    sim, ans = find(SIMILAR, q0), find(ANSWER, q0)
    q_end = min(i for i in (sim, ans, len(lines)) if i >= 0)
    question = " ".join(ln.strip() for ln in lines[q0:q_end])
    similar = " ".join(ln.strip() for ln in lines[sim + 1 : ans]) if 0 <= sim < ans else ""
    sh = find(SHORT, max(ans, 0))
    det = find(DETAIL, max(sh, 0)) if sh >= 0 else -1
    short = " ".join(ln.strip() for ln in lines[sh + 1 : det if det > sh else sh + 12]) if sh >= 0 else ""
    body = "\n".join(lines[ans + 1 :]) if ans >= 0 else "\n".join(lines[q_end:])
    return question, similar, short, body


def parse(pdf: Path = PDF_PATH) -> list[Entry]:
    import pypdf

    pages = [p.extract_text() or "" for p in pypdf.PdfReader(pdf).pages]
    starts = [i for i in range(20, len(pages)) if "السؤال" in (ln.strip() for ln in pages[i].split("\n"))]
    out = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(pages)
        lines = _clean("\n".join(pages[s:e])).split("\n")
        question, similar, short, body = _split(lines)
        out.append(Entry(k + 1, s + 1, question.strip(" :•"), similar.strip(" :•"), short.strip(" :•"), body[:7000]))
    return out


def load() -> list[Entry]:
    """Parsed questions, from the JSON cache when it is newer than the PDF."""
    if JSON_PATH.exists() and JSON_PATH.stat().st_mtime >= PDF_PATH.stat().st_mtime:
        return [Entry(**d) for d in json.loads(JSON_PATH.read_text(encoding="utf-8"))]
    entries = parse()
    JSON_PATH.write_text(json.dumps([e.__dict__ for e in entries], ensure_ascii=False), encoding="utf-8")
    return entries


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
    return Index(load())


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
