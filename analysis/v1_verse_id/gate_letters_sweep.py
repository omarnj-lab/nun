# Sweep the reading path's minimum letters on the internal set (production gate otherwise unchanged).
import csv
import json
from pathlib import Path

from nun import reading
from analysis.v1_verse_id.production_gate_eval import right

FIC = Path("data/private/fic")
labels = {r["file"]: r for r in csv.DictReader(open(FIC / "labels.csv", encoding="utf-8"))}
rows = [json.loads(x) for x in (FIC / "structured.jsonl").read_text(encoding="utf-8").splitlines()]
print("| min letters | shown | right | wrong | wrong % of all | naskh shown | naskh wrong |")
print("|---|---|---|---|---|---|---|")
for m in (15, 20, 25, 30, 35, 40):
    reading.MIN_LETTERS = m
    shown = ok = bad = ns = nb = 0
    for r in rows:
        d = reading.decide(r)
        if d["status"] != "read":
            continue
        lab = labels[r["file"]]
        good = right(lab, d)
        shown += 1
        ok += good
        bad += not good
        if lab["style"] == "naskh":
            ns += 1
            nb += not good
    print(f"| {m} | {shown} | {ok} | {bad} | {100 * bad / len(rows):.1f}% | {ns}/60 | {nb} |")
