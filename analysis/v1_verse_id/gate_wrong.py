# List the reading-path verses shown, right and wrong, with the gate's signals (internal set).
import csv
import json
from pathlib import Path

from nun import reading
from nun.retrieval.verse_search import searcher
from analysis.v1_verse_id.production_gate_eval import right

FIC = Path("data/private/fic")
labels = {r["file"]: r for r in csv.DictReader(open(FIC / "labels.csv", encoding="utf-8"))}
for x in (FIC / "structured.jsonl").read_text(encoding="utf-8").splitlines():
    r = json.loads(x)
    d = reading.decide(r)
    if d["status"] != "read":
        continue
    lab = labels[r["file"]]
    ok = right(lab, d)
    lines = [g["text"] for g in r["regions"] if g.get("text")]
    best, hits = searcher().read(lines)
    strong = [h for h in hits if not h.basmala and h.qlen >= 8]
    print(
        ("OK   " if ok else "WRONG"),
        lab["style"],
        f"want {lab['sura']}:{lab['aya_from']}",
        f"got {d['sura']}:{d['aya_from']}",
        f"score {d['score']} letters {d['letters']} lines {len(lines)} strong {len(strong)} regions {len(r['regions'])}",
    )
