"""Compare two runs of khattvision_quranic_eval.py (e.g. RES=448 vs RES=896): group metrics + per-image changes."""

import json
import re
import statistics as st
import sys
import unicodedata

from jiwer import cer

A_DIR, B_DIR = (sys.argv[1:3] + ["data/eval_quranic", "data/eval_quranic_896"][len(sys.argv[1:3]) :])[:2]
DIAC = re.compile("[ً-ٰٟۖ-ۭ]")


def norm(t: str) -> str:  # the notebook's normalize_arabic
    t = unicodedata.normalize("NFKC", str(t))
    t = DIAC.sub("", t)
    t = re.sub("[إأآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    t = re.sub(r"[^؀-ۿ0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip() or "∅"


a = json.load(open(f"{A_DIR}/quranic_ocr_metrics.json", encoding="utf-8"))
b = json.load(open(f"{B_DIR}/quranic_ocr_metrics.json", encoding="utf-8"))
print(f"{'group':30} {'n':>4} | CER (A → B)     | exact (A → B)    | chrF2 (A → B)")
for g in a:
    x, y = a[g], b[g]
    print(
        f"{g:30} {int(x['samples']):4} | {x['cer_normalized']:.3f} → {y['cer_normalized']:.3f} | "
        f"{x['exact_match_normalized']:6.1%} → {y['exact_match_normalized']:6.1%} | "
        f"{x['chrf2_normalized']:5.1f} → {y['chrf2_normalized']:5.1f}"
    )


def load(d: str) -> dict:
    with open(f"{d}/quranic_ocr_predictions.jsonl", encoding="utf-8") as f:
        return {r["image_id"]: r for r in map(json.loads, f) if not r.get("error")}


A, B = load(A_DIR), load(B_DIR)
held = [k for k in A if A[k]["original_split"] != "train"]
ca = {k: cer(norm(A[k]["reference"]), norm(A[k]["prediction"])) for k in held}
cb = {k: cer(norm(B[k]["reference"]), norm(B[k]["prediction"])) for k in held}
n = len(held)
print(
    f"\nheld-out per image (n={n}): median CER {st.median(ca.values()):.2f} → {st.median(cb.values()):.2f} · "
    f"near-perfect (CER≤0.10) {sum(v <= 0.1 for v in ca.values()) / n:.0%} → {sum(v <= 0.1 for v in cb.values()) / n:.0%} · "
    f"runaway (CER>1) {sum(v > 1 for v in ca.values()) / n:.0%} → {sum(v > 1 for v in cb.values()) / n:.0%}"
)
better = sum(cb[k] < ca[k] - 0.05 for k in held)
worse = sum(cb[k] > ca[k] + 0.05 for k in held)
print(f"held-out images: better {better} · worse {worse} · about the same {n - better - worse}")
