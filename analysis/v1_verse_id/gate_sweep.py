# Sweep reading-path gates on the cached KhattVision readings (internal set): how many verses shown vs wrong shown.
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import verse_id_eval as V  # noqa: E402

rows = list(csv.DictReader(open("data/private/fic/v1_scores.csv", encoding="utf-8")))


def correct(pred_ref, r):
    s, a0, a1 = V._span(pred_ref)
    want = {(int(r["sura"]), a) for a in range(int(r["aya_from"]), int(r["aya_to"]) + 1)}
    got = {(s, a) for a in range(a0, a1 + 1)}
    if want & got:
        return True
    return bool(set(V.ref_text(pred_ref).split()) and V.norm(V.ref_text(pred_ref)) == V.norm(r["uthmani_text"]))


def gate(reading, min_score, min_len, agree):
    best, locs = V.primary(reading)
    if not best or best["score"] < min_score or best["qlen"] < min_len or best["basmala"]:
        return None
    if agree:
        s, a0, a1 = V._span(best["ref"])
        for l in locs:
            if l["basmala"] or l["qlen"] < 8 or l is best:
                continue
            s2, b0, b1 = V._span(l["ref"])
            if l["score"] >= 80 and not (s2 == s and b0 <= a1 + 2 and a0 <= b1 + 2):
                return None  # a strong line points elsewhere
    return best["ref"]


print("| gate | style | shown | right | wrong (of all) |")
print("|---|---|---|---|---|")
for ms, ml, ag in [(90, 8, False), (90, 15, True), (93, 15, True), (95, 15, True), (95, 20, True), (97, 20, True)]:
    for style in ["naskh", "thuluth", "diwani", "ALL"]:
        g = [r for r in rows if style == "ALL" or r["style"] == style]
        shown = right = 0
        for r in g:
            ref = gate(r["reading"], ms, ml, ag)
            if ref:
                shown += 1
                right += correct(ref, r)
        print(
            f"| score≥{ms} len≥{ml} agree={ag} | {style} | {100 * shown / len(g):.0f}% | {100 * right / len(g):.0f}% | {100 * (shown - right) / len(g):.1f}% |"
        )
