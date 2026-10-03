# Replays KhattVision OCR predictions through a Nūn-style closed-corpus search:
# can the reading identify the right verse, and how often would it confidently show a wrong one?
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

Q = json.load(open(Path(__file__).with_name("quran_uthmani_quranenc.json"), encoding="utf-8"))  # [sura, aya, uthmani]

MARKS = re.compile("[ؐ-ًؚ-ٟۖ-ۭـ]")


def norm(t, dagger="map"):
    t = unicodedata.normalize("NFKC", str(t))
    t = t.replace("ٰ", "ا" if dagger == "map" else "")
    t = MARKS.sub("", t)
    t = re.sub("[إأآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    t = re.sub("[^ء-ي ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


ns = lambda t: t.replace(" ", "")

# ---- corpus units: single ayahs + 2- and 3-ayah windows, two orthographic variants (dagger alef kept / dropped)
units = []  # (key_texts: tuple of canonical ayah texts, ref string, ns text)
by_sura = defaultdict(list)
for s, a, txt in Q:
    by_sura[s].append((a, txt))
for s, ayas in by_sura.items():
    for i in range(len(ayas)):
        for w in (1, 2, 3):
            if i + w > len(ayas):
                break
            chunk = ayas[i : i + w]
            canon = tuple(ns(norm(t, "drop")) for _, t in chunk)
            ref = f"{s}:{chunk[0][0]}" + (f"-{chunk[-1][0]}" if w > 1 else "")
            for var in ("map", "drop"):
                units.append((canon, ref, ns(" ".join(norm(t, var) for _, t in chunk))))


# char-3gram inverted index for candidate generation
def grams(t):
    return {t[i : i + 3] for i in range(max(0, len(t) - 2))}


index = defaultdict(list)
for ui, (_, _, t) in enumerate(units):
    for g in grams(t):
        index[g].append(ui)
BASMALA = ns(norm("بسم الله الرحمن الرحيم", "drop"))


def locate(segment):
    """best unit for a text segment -> dict(score, ref, canon, qlen) or None"""
    q = ns(norm(segment, "map"))
    if len(q) < 4:
        return None
    votes = defaultdict(int)
    for g in grams(q):
        for ui in index.get(g, ()):
            votes[ui] += 1
    cands = sorted(votes, key=votes.get, reverse=True)[:200]
    best = None
    for ui in cands:
        canon, ref, t = units[ui]
        sc = fuzz.partial_ratio(q, t) if len(q) <= len(t) else fuzz.ratio(q, t)
        # prefer the tightest unit at equal score (single ayah over windows)
        key = (sc, -len(t))
        if best is None or key > best[0]:
            best = (key, ui)
    if best is None:
        return None
    (sc, _), ui = best
    canon, ref, t = units[ui]
    return {
        "score": sc,
        "ref": ref,
        "canon": canon,
        "qlen": len(q),
        "basmala": fuzz.ratio(q, BASMALA) >= 85 and len(q) <= len(BASMALA) * 1.3,
    }


def segments(text):
    parts = [p for p in re.split(r"[\n\r]+", str(text)) if p.strip()]
    return parts or [str(text)]


def primary(text, min_score=0):
    """longest located non-basmala segment (falls back to basmala) -> located dict + all located"""
    locs = [l for l in (locate(s) for s in segments(text)) if l]
    if not locs:
        return None, []
    nonb = [l for l in locs if not l["basmala"]]
    pool = nonb or locs
    return max(pool, key=lambda l: (l["qlen"] * (l["score"] / 100), l["score"])), locs


def locate_top(segment, k=5):
    """locate(), but the k best distinct refs for one segment (same scoring and tie-break)."""
    q = ns(norm(segment, "map"))
    if len(q) < 4:
        return []
    votes = defaultdict(int)
    for g in grams(q):
        for ui in index.get(g, ()):
            votes[ui] += 1
    scored = []
    for ui in sorted(votes, key=votes.get, reverse=True)[:200]:
        canon, ref, t = units[ui]
        sc = fuzz.partial_ratio(q, t) if len(q) <= len(t) else fuzz.ratio(q, t)
        scored.append(((sc, -len(t)), ui))
    out, seen = [], set()
    for (sc, _), ui in sorted(scored, reverse=True):
        canon, ref, t = units[ui]
        if ref in seen:
            continue
        seen.add(ref)
        out.append(
            {
                "score": sc,
                "ref": ref,
                "canon": canon,
                "qlen": len(q),
                "basmala": fuzz.ratio(q, BASMALA) >= 85 and len(q) <= len(BASMALA) * 1.3,
            }
        )
        if len(out) == k:
            break
    return out


def _span(ref):
    s, ayas = ref.split(":")
    a0, a1 = (int(x) for x in (ayas.split("-") + [ayas])[:2])
    return int(s), a0, a1


def suggest(text, k=5):
    """Top-k DISTINCT verse suggestions for a whole reading: every segment's candidates, ranked like primary()
    (non-Basmala first, then qlen × score, tightest unit first); a window overlapping an already suggested
    ref (e.g. 20:114-115 after 20:114) is skipped, so the k suggestions are k different places."""
    cands = [l for s in segments(text) for l in locate_top(s, 40)]
    cands.sort(
        key=lambda l: (not l["basmala"], l["qlen"] * (l["score"] / 100), l["score"], -len(l["canon"])), reverse=True
    )
    out = []
    for l in cands:
        s, a0, a1 = _span(l["ref"])
        if any(s == s2 and a0 <= b1 and b0 <= a1 for s2, b0, b1 in (_span(o["ref"]) for o in out)):
            continue
        out.append(l)
        if len(out) == k:
            break
    return out


def ref_text(ref):
    """Uthmani text (verbatim QuranEnc) for '2:255' or '2:255-256'."""
    s, ayas = ref.split(":")
    a0, a1 = (int(x) for x in (ayas.split("-") + [ayas])[:2])
    return " ".join(t for (ss, a, t) in Q if ss == int(s) and a0 <= a <= a1)


if __name__ == "__main__":  # the original evaluation; importing only exposes the search functions
    PRED = sys.argv[1] if len(sys.argv) > 1 else "/Users/omer/Downloads/quranic_ocr_predictions.csv"
    df = pd.read_csv(PRED)
    rows = []
    for r in df.itertuples():
        g, gall = primary(r.reference)
        p, pall = primary(r.prediction if isinstance(r.prediction, str) else "")
        gold_ok = g is not None and g["score"] >= 85 and g["qlen"] >= 6
        correct = bool(gold_ok and p and set(p["canon"]) & set(g["canon"]))
        rows.append(
            {
                "image_id": r.image_id,
                "split": r.original_split,
                "style": r.style,
                "gold_ref": g["ref"] if g else None,
                "gold_score": g["score"] if g else 0,
                "gold_ok": gold_ok,
                "gold_basmala_only": bool(g and g["basmala"]),
                "pred_ref": p["ref"] if p else None,
                "pred_score": p["score"] if p else 0,
                "pred_len": p["qlen"] if p else 0,
                "correct": correct,
                "reference": r.reference,
                "prediction": r.prediction,
            }
        )
    R = pd.DataFrame(rows)
    R.to_csv("verse_id_results.csv", index=False, encoding="utf-8-sig")

    def report(name, F):
        F = F[F.gold_ok]
        n = len(F)
        out = {"set": name, "images_with_locatable_gold": n, "verse_id_top1": round(F.correct.mean(), 3)}
        for T in (80, 90, 95):
            ans = F[(F.pred_score >= T) & (F.pred_len >= 8)]
            out[f"answered@{T}"] = round(len(ans) / n, 3)
            out[f"precision@{T}"] = round(ans.correct.mean(), 3) if len(ans) else None
            out[f"confident_wrong@{T}"] = round(((~ans.correct).sum()) / n, 3)
        return out

    table = [
        report("held-out (val+test)", R[R.split != "train"]),
        report("test only", R[R.split == "test"]),
        report("train-seen", R[R.split == "train"]),
    ]
    print(pd.DataFrame(table).T.to_string())
    print(
        "\nlocatable gold share  held-out:",
        round(R[R.split != "train"].gold_ok.mean(), 3),
        " train:",
        round(R[R.split == "train"].gold_ok.mean(), 3),
    )
    H = R[(R.split != "train") & R.gold_ok]
    print("\nheld-out by style (verse_id_top1, n, confident_wrong@90):")
    for st, F in H.groupby("style"):
        if len(F) >= 5:
            ans = F[(F.pred_score >= 90) & (F.pred_len >= 8)]
            print(
                f"  {st:12} n={len(F):3}  top1={F.correct.mean():.2f}  answered@90={len(ans)/len(F):.2f}  "
                f"prec@90={(ans.correct.mean() if len(ans) else float('nan')):.2f}  confident_wrong@90={(~ans.correct).sum()/len(F):.2f}"
            )
    print(
        "\nheld-out: gold is Basmala only:",
        int(H.gold_basmala_only.sum()),
        "of",
        len(H),
        "| correct among non-basmala gold:",
        round(H[~H.gold_basmala_only].correct.mean(), 3),
    )
