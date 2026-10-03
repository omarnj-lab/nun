"""The product panel collection: panels whose verse the team confirmed AND that may be shown publicly.

data/collection/collection.json + data/collection/images/ (git-ignored). Each panel: id, file, sura, aya_from, aya_to,
text_box (fractions x0, y0, x1, y1, or null = middle 60%), source, added_at. Commons, FIC, DuwatBench and
can_show_publicly = no photos never enter this collection.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageOps

from nun.corpus.store import CorpusStore

ROOT = Path("data/collection")
INDEX = ROOT / "collection.json"
_lock = threading.Lock()
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,60}$")


def load() -> list[dict]:
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else []


def save(panels: list[dict]) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    tmp = INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(panels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(INDEX)


def check_ref(store: CorpusStore, sura: int, aya_from: int, aya_to: int) -> None:
    if aya_to < aya_from:
        raise ValueError("aya_to < aya_from")
    store.range(sura, aya_from, aya_to)  # KeyError when the reference does not exist


def check_box(box) -> tuple[float, float, float, float] | None:
    if box is None:
        return None
    x0, y0, x1, y1 = (float(v) for v in box)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1) or (x1 - x0) * (y1 - y0) < 0.01:
        raise ValueError("text box must be inside the photo and cover at least 1% of it")
    return (round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4))


def add(
    store: CorpusStore,
    panel_id: str,
    image: Image.Image,
    sura: int,
    aya_from: int,
    aya_to: int,
    text_box=None,
    source: str = "admin",
) -> dict:
    if not ID_RE.match(panel_id):
        raise ValueError("id: lowercase letters, digits, - and _ only")
    check_ref(store, sura, aya_from, aya_to)
    box = check_box(text_box)
    with _lock:
        panels = load()
        if any(p["id"] == panel_id for p in panels):
            raise ValueError(f"panel {panel_id} already exists")
        (ROOT / "images").mkdir(parents=True, exist_ok=True)
        file = f"{panel_id}.jpg"
        im = ImageOps.exif_transpose(image).convert("RGB")
        im.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
        im.save(ROOT / "images" / file, quality=92)
        rec = {
            "id": panel_id,
            "file": file,
            "sura": sura,
            "aya_from": aya_from,
            "aya_to": aya_to,
            "text_box": box,
            "source": source,
            "added_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        save([*panels, rec])
        return rec


def remove(panel_id: str) -> bool:
    with _lock:
        panels = load()
        keep = [p for p in panels if p["id"] != panel_id]
        if len(keep) == len(panels):
            return False
        (ROOT / "images" / f"{panel_id}.jpg").unlink(missing_ok=True)
        save(keep)
        return True


def seed_from_team(store: CorpusStore, team_dir: Path = Path("data/real_test")) -> int:
    """Add the team's panels with can_show_publicly = yes (verses confirmed by the team). Idempotent."""
    existing = {p["id"] for p in load()}
    n = 0
    for r in csv.DictReader((team_dir / "panels.csv").open(encoding="utf-8")):
        if r["can_show_publicly"].strip().lower() != "yes":
            continue  # testing only: never in the public collection
        pid = r["panel"].lower()
        if pid in existing:
            continue
        src = team_dir / "collection" / r["file"]
        im = Image.open(src)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            white = Image.new("RGBA", im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(white, im)
        add(store, pid, im, int(r["sura"]), int(r["aya_from"]), int(r["aya_to"]), None, source=r["kind"])
        n += 1
    return n


def images_dir() -> Path:
    return ROOT / "images"


def copy_out(dest: Path) -> None:  # used for backups / the small open dataset later
    shutil.copytree(ROOT, dest, dirs_exist_ok=True)
