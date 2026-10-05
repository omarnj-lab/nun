"""The visitor's learning journey after a verse card (Track 03): context, next stops, a short understanding check.

Everything here is built from approved data only (corpus text verbatim, the approved translation, Tanzil metadata,
the team's collection). Quiz results are stored as anonymous counts (no identifiers, no IP, no free text).
"""

from __future__ import annotations

import json
import random
import threading
import time
from functools import lru_cache
from pathlib import Path

from nun import collection
from nun.card import build as build_card
from nun.corpus.store import CorpusStore

PUBLIC_PANELS = Path("apps/web/public/panels")  # small public copies (can_show_publicly = yes)
RESULTS = Path("data/quiz/results.jsonl")
_lock = threading.Lock()


def _ayah(store: CorpusStore, sura: int, aya: int, lang: str) -> dict | None:
    try:
        c = build_card(store, sura, aya, aya, lang)
    except KeyError:
        return None
    a = c["ayahs"][0]
    return {
        "sura": sura,
        "aya": aya,
        "label": c["ref"]["label"],
        "text_display": a["text_display"],
        "translation": a["translation"],
        "audio": a["audio"],
    }


def _panel_public(pid: str) -> str | None:
    return f"/panels/{pid}.jpg" if (PUBLIC_PANELS / f"{pid}.jpg").exists() else None


def journey(store: CorpusStore, sura: int, aya_from: int, aya_to: int, lang: str, panel_id: str | None) -> dict:
    """Previous/next ayah (verbatim) and the collection's other panels from the same surah (the next stops)."""
    count = sum(1 for r in store.all() if r.sura == sura)
    prev = _ayah(store, sura, aya_from - 1, lang) if aya_from > 1 else None
    nxt = _ayah(store, sura, aya_to + 1, lang) if aya_to < count else None
    stops = []
    for p in collection.load():
        if p["id"] == panel_id or p["sura"] != sura:
            continue
        img = _panel_public(p["id"])
        if not img:
            continue
        relation = "next" if p["aya_from"] == aya_to + 1 else "before" if p["aya_to"] == aya_from - 1 else "same_surah"
        stops.append(
            {
                "id": p["id"],
                "sura": p["sura"],
                "aya_from": p["aya_from"],
                "aya_to": p["aya_to"],
                "image": img,
                "relation": relation,
            }
        )
    stops.sort(key=lambda s: (s["relation"] != "next", s["aya_from"]))
    return {"surah_ayahs": count, "prev": prev, "next": nxt, "stops": stops}


@lru_cache
def _surahs(path: str = "data/corpus/quran.jsonl") -> list[dict]:
    seen: dict[int, dict] = {}
    for r in CorpusStore(path).all():
        s = seen.setdefault(
            r.sura,
            {
                "sura": r.sura,
                "ar": r.sura_name_ar,
                "en": r.sura_name_en,
                "ayahs": 0,
                "revelation": r.revelation,
                "juz": r.juz,
            },
        )
        s["ayahs"] += 1
    return [seen[k] for k in sorted(seen)]


def quran_map() -> list[dict]:
    """114 surahs: names, ayah counts, Meccan/Medinan, first juz (Tanzil metadata) for the 'where in the Quran' view."""
    return _surahs()


def quiz(store: CorpusStore, sura: int, aya_from: int, aya_to: int, seed: int | None = None) -> dict:
    """Three questions with options from approved data: surah, Meccan/Medinan, meaning (approved translation)."""
    rng = random.Random(seed if seed is not None else (sura * 1000 + aya_from))
    card = build_card(store, sura, aya_from, aya_to, "en")
    surahs = _surahs()
    others = [s for s in surahs if s["sura"] != sura]
    names = rng.sample(others, 3) + [next(s for s in surahs if s["sura"] == sura)]
    rng.shuffle(names)
    q_surah = [{"ar": s["ar"], "en": s["en"], "correct": s["sura"] == sura} for s in names]
    q_rev = [{"key": k, "correct": k == card["revelation"]} for k in ("meccan", "medinan")]

    meaning = " ".join((a["translation"] or "") for a in card["ayahs"])
    pool = [p for p in collection.load() if p["sura"] != sura]
    rng.shuffle(pool)
    distractors = []
    for p in pool:
        t = " ".join(
            (a["translation"] or "") for a in build_card(store, p["sura"], p["aya_from"], p["aya_to"], "en")["ayahs"]
        )
        if t and t not in distractors:
            distractors.append(t)
        if len(distractors) == 2:
            break
    q_meaning = [{"text": meaning, "correct": True}] + [{"text": t, "correct": False} for t in distractors]
    rng.shuffle(q_meaning)
    return {
        "translator": card["translation"]["translator"] if card["translation"] else None,
        "questions": [
            {"id": "meaning", "options": q_meaning},
            {"id": "surah", "options": q_surah},
            {"id": "revelation", "options": q_rev},
        ],
    }


def record(panel_id: str | None, sura: int, aya: int, lang: str, pre: bool | None, post: int, total: int) -> None:
    """Anonymous result: no identifiers; time rounded to the hour."""
    row = {
        "t": int(time.time() // 3600 * 3600),
        "panel": panel_id,
        "ref": f"{sura}:{aya}",
        "lang": lang[:5],
        "pre_correct": pre,
        "post_correct": int(post),
        "post_total": int(total),
    }
    with _lock:
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        with RESULTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


def stats() -> dict:
    rows = []
    if RESULTS.exists():
        rows = [json.loads(x) for x in RESULTS.read_text(encoding="utf-8").splitlines() if x.strip()]
    pre = [r["pre_correct"] for r in rows if r["pre_correct"] is not None]
    meaning_post = [r for r in rows if r["post_total"]]
    return {
        "sessions": len(rows),
        "pre_guess_correct_%": round(100 * sum(pre) / len(pre), 1) if pre else None,
        "post_quiz_correct_%": round(
            100 * sum(r["post_correct"] for r in meaning_post) / sum(r["post_total"] for r in meaning_post), 1
        )
        if meaning_post
        else None,
        "with_pre_guess": len(pre),
    }
