"""Demo panels, steps 3–4: top-5 verse suggestions per reading → data/panels/review.csv.

Suggestions come from analysis/v1_verse_id/verse_id_eval.py (quran_uthmani_quranenc.json, its normalisation, single
ayahs + 2–3-ayah windows, fuzzy partial matching), via its suggest(): five DISTINCT places. Re-running keeps the
human columns (confirmed_ref, type, panel_group, notes) already filled in review.csv.

    PYTHONPATH=. python scripts/panels_suggest.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis" / "v1_verse_id"))
import verse_id_eval as vid  # noqa: E402

PANELS = Path("data/panels")
REVIEW = PANELS / "review.csv"
HUMAN = ["confirmed_ref", "type", "panel_group", "notes"]
FIELDS = ["file", "license", "author", "url", "reading"] + [f"suggestion_{i}" for i in range(1, 6)] + HUMAN


def main() -> None:
    cands = list(csv.DictReader((PANELS / "candidates.csv").open(encoding="utf-8")))
    readings = {}
    for r in map(json.loads, (PANELS / "readings.jsonl").open(encoding="utf-8")):
        if not r.get("error"):
            readings[r["file"]] = r["reading"]
    old = {r["file"]: r for r in csv.DictReader(REVIEW.open(encoding="utf-8"))} if REVIEW.exists() else {}
    rows, with_sugg = [], 0
    for c in cands:
        reading = readings.get(c["file"], "")
        sugg = vid.suggest(reading) if reading else []
        with_sugg += bool(sugg)
        row = {
            "file": c["file"],
            "license": c["license"],
            "author": c["author"] or c["credit"],
            "url": c["url"],
            "reading": reading,
        }
        for i in range(5):
            row[f"suggestion_{i + 1}"] = f"{sugg[i]['ref']} — {vid.ref_text(sugg[i]['ref'])}" if i < len(sugg) else ""
        for h in HUMAN:
            row[h] = old.get(c["file"], {}).get(h, "")
        rows.append(row)
    with REVIEW.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} panels · {len(readings)} read · {with_sugg} with at least one suggestion → {REVIEW}")


if __name__ == "__main__":
    main()
