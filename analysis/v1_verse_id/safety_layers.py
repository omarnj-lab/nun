# Model-first pipeline + candidate safety layers, measured on the internal set from cached outputs:
#   candidate  = KhattVision structured reading -> nearest Quran passage (any script)
#   self       = KhattVision's plain OCR prompt (a second, independent reading) lands on the same passage
#   claude     = Claude Opus 5, asked independently which verse the image shows, names the same passage
import csv
import json
from pathlib import Path

from analysis.v1_verse_id.production_gate_eval import right
from eval.recognition_compare import parse
from nun.retrieval.verse_search import searcher

FIC = Path("data/private/fic")
labels = {r["file"]: r for r in csv.DictReader(open(FIC / "labels.csv", encoding="utf-8"))}
structured = {
    json.loads(x)["file"]: json.loads(x) for x in (FIC / "structured.jsonl").read_text(encoding="utf-8").splitlines()
}
ocr = {r["file"]: r["reading"] for r in csv.DictReader(open(FIC / "v1_scores.csv", encoding="utf-8"))}
claude = {}
for x in (FIC / "compare_cache" / "claude-opus-5.jsonl").read_text(encoding="utf-8").splitlines():
    d = json.loads(x)
    claude[d["file"]] = parse(d["raw"])
S = searcher()


def cand(f, min_letters):
    r = structured[f]
    if r.get("theme") not in (None, "quranic"):
        return None
    best, _ = S.read([g["text"] for g in r.get("regions", []) if g.get("text")])
    if not best or best.basmala or best.score < 90 or best.qlen < min_letters:
        return None
    return best


def same(h, sura, a0, a1):
    return h.sura == sura and h.aya_from <= a1 and a0 <= h.aya_to


def self_ok(f, h):
    o, _ = S.read([s for s in ocr[f].split("\n") if s.strip()])
    return bool(o and not o.basmala and o.score >= 85 and same(h, o.sura, o.aya_from, o.aya_to))


def claude_ok(f, h):
    c = claude.get(f)
    return bool(c and same(h, c["sura"], c["aya_from"], c["aya_to"]))


rules = {
    "model only": lambda f, h: True,
    "model + self-check": self_ok,
    "model + claude check": claude_ok,
    "model + (self or claude)": lambda f, h: self_ok(f, h) or claude_ok(f, h),
}
print("| min letters | rule | style | shown | right | wrong (% of panels) |")
print("|---|---|---|---|---|---|")
for ml in (15, 30):
    for name, rule in rules.items():
        for style in ("naskh", "thuluth", "diwani", "ALL"):
            fs = [f for f in labels if style == "ALL" or labels[f]["style"] == style]
            shown = ok = 0
            for f in fs:
                h = cand(f, ml)
                if h and rule(f, h):
                    shown += 1
                    ok += right(labels[f], {"sura": h.sura, "aya_from": h.aya_from, "aya_to": h.aya_to})
            print(
                f"| {ml} | {name} | {style} | {100 * shown / len(fs):.0f}% | {100 * ok / len(fs):.0f}% | {100 * (shown - ok) / len(fs):.1f}% |"
            )
