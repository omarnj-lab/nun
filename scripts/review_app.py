"""Demo panels, step 5: local review app for data/panels/review.csv (binds to 127.0.0.1 only).

    PYTHONPATH=. ~/.venvs/nun/bin/uvicorn scripts.review_app:app --host 127.0.0.1 --port 8766
    → http://127.0.0.1:8766

Each panel is shown large with its 5 verse suggestions as buttons; a search box over the Quran (Arabic words or a
reference such as 2:255 / 2:255-256) when none is right; buttons for Name of Allah / dhikr / not Quran-other; and
"same panel as #…" to group photos of one physical panel. Every choice is written to review.csv immediately.
"""

from __future__ import annotations

import csv
import os
import re
import sys
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis" / "v1_verse_id"))
import verse_id_eval as vid  # noqa: E402

PANELS = Path("data/panels")
REVIEW = PANELS / "review.csv"
TYPES = ["quran", "name_of_allah", "dhikr", "other"]
_lock = threading.Lock()
app = FastAPI(title="Nūn panel review")

# search index: (sura, aya, uthmani, normalised text) for every ayah
AYAHS = [(s, a, t, vid.norm(t, "drop")) for s, a, t in vid.Q]
AYAHS_MAP = {(s, a): vid.norm(t, "map") for s, a, t in vid.Q}


def load() -> tuple[list[str], list[dict]]:
    with REVIEW.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def save(fields: list[str], rows: list[dict]) -> None:
    fd, tmp = tempfile.mkstemp(dir=PANELS, suffix=".csv")  # atomic replace: a crash never leaves half a file
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, REVIEW)


def group_id(i: int) -> str:
    return f"P{i + 1:03d}"


def status(r: dict) -> str:
    return "done" if r["type"] else "todo"


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    return PAGE


@app.get("/img/{name}")
def img(name: str) -> FileResponse:
    p = (PANELS / "raw" / name).resolve()
    if (PANELS / "raw").resolve() not in p.parents or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/panels")
def panels() -> dict:
    _, rows = load()
    return {"panels": [{"n": i + 1, "status": status(r), "type": r["type"]} for i, r in enumerate(rows)]}


@app.get("/api/panel/{n}")
def panel(n: int) -> dict:
    _, rows = load()
    if not 1 <= n <= len(rows):
        raise HTTPException(404)
    r = rows[n - 1]
    sugg = []
    for i in range(1, 6):
        cell = r.get(f"suggestion_{i}") or ""
        if cell:
            ref, _, text = cell.partition(" — ")
            sugg.append({"ref": ref, "text": text})
    return {"n": n, "total": len(rows), "row": r, "suggestions": sugg}


REF = re.compile(r"^\s*(\d{1,3})\s*[:：]\s*(\d{1,3})(?:\s*-\s*(\d{1,3}))?\s*$")


@app.get("/api/search")
def search(q: str) -> dict:
    """A reference (2:255, 2:255-256), or Arabic words: exact normalised substring first, then fuzzy suggestions."""
    m = REF.match(q)
    if m:
        s, a0 = int(m[1]), int(m[2])
        a1 = int(m[3] or a0)
        ref = f"{s}:{a0}" + (f"-{a1}" if a1 != a0 else "")
        text = vid.ref_text(ref)
        return {"results": [{"ref": ref, "text": text}] if text else []}
    qn = vid.norm(q, "drop")
    qm = vid.norm(q, "map")
    if len(qn) < 3:
        return {"results": []}
    hits = [{"ref": f"{s}:{a}", "text": t} for s, a, t, n in AYAHS if qn in n or qm in AYAHS_MAP[(s, a)]][:20]
    if not hits:
        hits = [{"ref": x["ref"], "text": vid.ref_text(x["ref"])} for x in vid.suggest(q, k=10)]
    return {"results": hits}


class Choice(BaseModel):
    type: str
    confirmed_ref: str = ""
    notes: str | None = None
    same_as: int | None = None


@app.post("/api/panel/{n}")
def choose(n: int, c: Choice) -> dict:
    if c.type not in TYPES:
        raise HTTPException(422, f"type must be one of {TYPES}")
    if c.type == "quran" and not vid.ref_text(c.confirmed_ref or "0:0"):
        raise HTTPException(422, "a Quran choice needs a valid reference, e.g. 2:255 or 2:255-256")
    with _lock:
        fields, rows = load()
        if not 1 <= n <= len(rows):
            raise HTTPException(404)
        r = rows[n - 1]
        r["type"], r["confirmed_ref"] = c.type, (c.confirmed_ref if c.type == "quran" else "")
        if c.notes is not None:
            r["notes"] = c.notes
        if c.same_as:
            if not 1 <= c.same_as <= len(rows) or c.same_as == n:
                raise HTTPException(422, "same panel as: give another panel number")
            other = rows[c.same_as - 1]
            other["panel_group"] = other["panel_group"] or group_id(c.same_as - 1)
            r["panel_group"] = other["panel_group"]
        elif not r["panel_group"]:
            r["panel_group"] = group_id(n - 1)
        save(fields, rows)
        return {"ok": True, "row": r}


PAGE = (Path(__file__).parent / "review_app.html").read_text(encoding="utf-8")
