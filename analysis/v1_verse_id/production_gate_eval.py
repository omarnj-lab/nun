# Score the production reading path (nun.reading.decide on KhattVision's structured output) on the internal set:
# per labelled style: verses shown, right, wrong; plus how often KhattVision's own style/theme labels are right.
# Input: data/private/fic/structured.jsonl (analysis/v1_verse_id/structured_run.py). Internal images only.
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from nun import reading
from nun.corpus.store import CorpusStore
from nun.normalize.arabic import normalize_ns

FIC = Path("data/private/fic")
store = CorpusStore()
labels = {r["file"]: r for r in csv.DictReader(open(FIC / "labels.csv", encoding="utf-8"))}
rows = [json.loads(x) for x in (FIC / "structured.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
STYLE_OF = {
    "naskh": "Naskh",
    "thuluth": "Thuluth",
    "diwani": "Diwani",
    "diwani-jelli": "Diwani",
    "fatimi-kufic-script": "Kufic",
    "square-kufic": "Kufic",
    "muhaqaq": "Thuluth",
}


def texts(s, a, b):
    out = set()
    for x in range(a, b + 1):
        try:
            out.add(normalize_ns(store.get(s, x).text_simple))
        except KeyError:
            pass
    return out


def right(lab, d):
    return bool(
        texts(int(lab["sura"]), int(lab["aya_from"]), int(lab["aya_to"])) & texts(d["sura"], d["aya_from"], d["aya_to"])
    )


stats = defaultdict(Counter)
style_conf = Counter()
for r in rows:
    if "error" in r:
        continue
    lab = labels[r["file"]]
    d = reading.decide(r)
    g = lab["style"]
    for key in (g, "ALL"):
        st = stats[key]
        st["n"] += 1
        st[d["status"]] += 1
        st[f"reason:{d['reason']}"] += 1
        if d["status"] == "read":
            st["right" if right(lab, d) else "wrong"] += 1
        st["theme_quranic"] += r.get("theme") == "quranic"
        st["style_ok"] += STYLE_OF.get(g, "?") in (r.get("styles") or [])
    style_conf[(g, tuple(r.get("styles") or []))] += 1

print(f"scored {sum(1 for r in rows if 'error' not in r)} / {len(labels)} images\n")
print(
    "| label style | n | verse shown | right | **wrong shown** | not-Quranic said | model style right | model says quranic |"
)
print("|---|---|---|---|---|---|---|---|")
for k in ["naskh", "thuluth", "diwani", "diwani-jelli", "fatimi-kufic-script", "square-kufic", "muhaqaq", "ALL"]:
    st = stats.get(k)
    if not st:
        continue
    n = st["n"]
    print(
        f"| {k} | {n} | {100 * st['read'] / n:.0f}% | {100 * st['right'] / n:.0f}% | {100 * st['wrong'] / n:.1f}% | "
        f"{100 * st['not_quranic'] / n:.0f}% | {100 * st['style_ok'] / n:.0f}% | {100 * st['theme_quranic'] / n:.0f}% |"
    )
print("\nreasons (ALL):", {k: v for k, v in stats["ALL"].items() if k.startswith("reason:")})
print(
    "\nstyle predictions for labelled naskh:",
    Counter(s for (g, s), c in style_conf.items() for _ in range(c) if g == "naskh"),
)
