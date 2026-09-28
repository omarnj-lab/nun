"""M3 labelling tool for the real-test set (local only; binds to 127.0.0.1).

    make label            # then open http://127.0.0.1:8765

Label mode: type what you read → "Find" locates it in the Quran corpus / Names / dhikr lists → tick the matching
reference(s) → style + theme → Save. Or mark the image "other" (not Quran/Name/dhikr) or "skip" (unusable).
Review mode: a second person confirms or rejects each label (SPEC §10: every label reviewed by a second person).

Every action is appended to eval/sets/real-test.labels.jsonl (the log is the source of truth; the latest entry per
image wins). `make realtest` compiles the reviewed labels into eval/sets/real-test.jsonl.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from nun.corpus.fragment import QuranIndex, locate_fuzzy, ref_key, ref_str
from nun.corpus.store import CorpusStore
from nun.normalize.arabic import normalize, normalize_ns

CANDIDATES = Path("data/real/commons/candidates.jsonl")
IMAGES = Path("data/real/commons")
LOG = Path("eval/sets/real-test.labels.jsonl")
LISTS = Path("data/lists")
STYLES = ["Thuluth", "Diwani", "Naskh", "Kufic", "Ruq'ah", "Nasta'liq"]
THEMES = [
    "dedication",
    "devotional invocation",
    "hadith",
    "names of Allah",
    "names of companions",
    "names of the Prophet",
    "non-religious",
    "personal/place name",
    "quranic",
]

app = FastAPI(title="Nūn labelling tool")


def image_id(c: dict) -> str:
    return "rt-" + c["sha1_original"][:12]


@lru_cache
def store() -> CorpusStore:
    return CorpusStore()


@lru_cache
def index() -> QuranIndex:
    return QuranIndex(store())


@lru_cache
def lists() -> dict[str, list[dict]]:
    out = {}
    for kind in ("names", "dhikr"):
        p = LISTS / f"{kind}.draft.jsonl"
        out[kind] = [json.loads(line) for line in p.open(encoding="utf-8")] if p.exists() else []
    return out


def candidates() -> list[dict]:
    if not CANDIDATES.exists():
        return []
    return [json.loads(line) for line in CANDIDATES.open(encoding="utf-8")]


def state() -> dict[str, dict]:
    """Latest label and latest review per image id, folded from the append-only log."""
    out: dict[str, dict] = {}
    if LOG.exists():
        for line in LOG.open(encoding="utf-8"):
            e = json.loads(line)
            s = out.setdefault(e["id"], {})
            if e["event"] == "label":
                s.pop("review", None)  # a new label invalidates an earlier review
                s["label"] = e
            elif e["event"] == "review":
                s["review"] = e
    return out


def append(event: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["at"] = datetime.now(UTC).isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.get("/img/{name:path}")
def img(name: str) -> FileResponse:
    p = (IMAGES / name).resolve()
    if IMAGES.resolve() not in p.parents or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/meta")
def meta() -> dict:
    return {"styles": STYLES, "themes": THEMES}


@app.get("/api/stats")
def stats() -> dict:
    st, cands = state(), candidates()
    labelled = [s["label"] for s in st.values() if "label" in s]
    reviewed = [s for s in st.values() if s.get("review", {}).get("verdict") == "confirm"]
    by_type: dict[str, int] = {}
    for lab in labelled:
        by_type[lab["gt_type"]] = by_type.get(lab["gt_type"], 0) + 1
    return {"candidates": len(cands), "labelled": len(labelled), "reviewed": len(reviewed), "by_type": by_type}


@app.get("/api/item")
def item(mode: Literal["label", "review"] = "label", who: str = "", skip: str = "") -> dict:
    st = state()
    skipped = set(filter(None, skip.split(",")))
    for c in candidates():
        cid = image_id(c)
        if cid in skipped:
            continue
        s = st.get(cid, {})
        rejected = s.get("review", {}).get("verdict") == "reject"
        if mode == "label" and ("label" not in s or rejected):
            # a rejected label comes back with the previous attempt and the reviewer's note
            return {"id": cid, "candidate": c, "previous": s.get("label"), "review": s.get("review")}
        if mode == "review" and "label" in s and "review" not in s and s["label"].get("gt_type") != "skip":
            if who and s["label"].get("labeller") == who:
                continue  # the second person must not be the labeller
            return {"id": cid, "candidate": c, "label": s["label"]}
    return {"id": None}


class LocateIn(BaseModel):
    text: str


@app.post("/api/locate")
def locate(q: LocateIn) -> dict:
    idx, q_ns = index(), normalize_ns(q.text)
    quran = []
    if len(q_ns) >= 2:
        hits = idx.find_exact(q_ns) or (idx.find_exact(q_ns, whole_words=False) if len(q_ns) >= 8 else [])
        spans = [idx.span(*h) for h in hits if not idx.span(*h)["cross_sura"]]
        match, score = "exact", 100.0
        if not spans and len(q_ns) >= 8:
            got = locate_fuzzy(idx, q_ns)
            if got and got[1] >= 70:
                spans, match, score = [got[0]], "fuzzy", round(got[1], 1)
        seen = set()
        for sp in spans:
            r = ref_str(sp)
            if r in seen:
                continue
            seen.add(r)
            recs = store().range(sp["sura"], sp["aya_from"], sp["aya_to"])
            quran.append(
                {
                    "ref": r,
                    "sura": sp["sura"],
                    "aya_from": sp["aya_from"],
                    "aya_to": sp["aya_to"],
                    "sura_name": recs[0].sura_name_ar,
                    "fragment": sp["fragment"],
                    "uthmani": " ".join(x.text_uthmani for x in recs),  # verbatim corpus text, for visual check
                    "match": match,
                    "score": score,
                }
            )
        quran.sort(key=lambda x: ref_key(x["ref"]))
    q_norm = normalize(q.text)
    names = [n for n in lists()["names"] if q_norm and (n["text_norm"] == q_norm or n["text_norm"] in q_norm.split())]
    dhikr = [d for d in lists()["dhikr"] if q_norm and d["text_norm"] in q_norm]
    return {
        "quran": quran[:25],
        "quran_total": len(quran),
        "names": [{"id": n["id"], "text": n["text"]} for n in names],
        "dhikr": [{"id": d["id"], "text": d["text"]} for d in dhikr],
    }


class Ref(BaseModel):
    sura: int
    aya_from: int
    aya_to: int


class LabelIn(BaseModel):
    id: str
    labeller: str = Field(min_length=1)
    gt_type: Literal["quran", "name", "dhikr", "other", "skip"]
    refs: list[Ref] = []
    list_ids: list[str] = []
    gt_text: str = ""
    style: list[str] = []
    theme: str | None = None
    notes: str = ""


@app.post("/api/label")
def label(x: LabelIn) -> dict:
    if x.gt_type == "quran" and not x.refs:
        raise HTTPException(422, "a quran label needs at least one reference")
    if x.gt_type in ("name", "dhikr") and not x.list_ids:
        raise HTTPException(422, "pick the Name / dhikr entry")
    if any(s not in STYLES for s in x.style) or (x.theme and x.theme not in THEMES):
        raise HTTPException(422, "unknown style/theme")
    for r in x.refs:
        try:
            store().range(r.sura, r.aya_from, r.aya_to)
        except KeyError as e:
            raise HTTPException(422, str(e)) from None
    append({"event": "label", **x.model_dump()})
    return {"ok": True}


class ReviewIn(BaseModel):
    id: str
    reviewer: str = Field(min_length=1)
    verdict: Literal["confirm", "reject"]
    notes: str = ""


@app.post("/api/review")
def review(x: ReviewIn) -> dict:
    s = state().get(x.id, {})
    if "label" not in s:
        raise HTTPException(404, "not labelled")
    if s["label"]["labeller"] == x.reviewer:
        raise HTTPException(422, "the reviewer must be a different person from the labeller")
    append({"event": "review", **x.model_dump()})
    return {"ok": True}
