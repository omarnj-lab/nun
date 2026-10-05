"""Can agreement between independent readers make verse recognition safe outside the collection?

Reads the cached answers of eval/recognition_compare.py (external models) and the KhaṭṭVision v1 readings, then
scores rules that show a verse only when two sources agree. Output stays in data/private (git-ignored).

    PYTHONPATH=. python eval/recognition_agreement.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from rapidfuzz import fuzz

from eval.recognition_compare import FIC, ayah_texts, is_correct, load_labels, parse
from nun.corpus.store import CorpusStore
from nun.normalize.arabic import normalize_ns


def cached(system: str) -> dict[str, dict | None]:
    rows = [json.loads(x) for x in (FIC / "compare_cache" / f"{system}.jsonl").read_text(encoding="utf-8").splitlines()]
    return {r["file"]: parse(r["raw"]) for r in rows}


def same(a: dict | None, b: dict | None, store: CorpusStore) -> bool:
    return bool(
        a
        and b
        and ayah_texts(store, a["sura"], a["aya_from"], a["aya_to"])
        & ayah_texts(store, b["sura"], b["aya_from"], b["aya_to"])
    )


def reading_supports(reading: str, pred: dict | None, store: CorpusStore, threshold: int) -> bool:
    """KhaṭṭVision's reading (from the pixels) agrees with the predicted verse's corpus text."""
    if not pred or not reading:
        return False
    target = "".join(sorted(ayah_texts(store, pred["sura"], pred["aya_from"], pred["aya_to"]), key=len))
    return fuzz.partial_ratio(normalize_ns(reading), target) >= threshold


def main() -> None:
    store = CorpusStore()
    labels = load_labels()
    claude, gpt = cached("claude-opus-5"), cached("gpt-5.5")
    with (FIC / "v1_scores.csv").open(encoding="utf-8") as f:
        reading = {r["file"]: r["reading"] for r in csv.DictReader(f)}
    rules = {
        "claude alone": lambda f: claude[f],
        "claude + gpt agree": lambda f: claude[f] if same(claude[f], gpt[f], store) else None,
        "claude + KhattVision reading ≥ 70": lambda f: (
            claude[f] if reading_supports(reading[f], claude[f], store, 70) else None
        ),
        "claude + KhattVision reading ≥ 80": lambda f: (
            claude[f] if reading_supports(reading[f], claude[f], store, 80) else None
        ),
        "claude + (gpt or reading ≥ 80)": lambda f: (
            claude[f] if same(claude[f], gpt[f], store) or reading_supports(reading[f], claude[f], store, 80) else None
        ),
    }
    lines = ["| rule | style | n | correct | shown | precision | wrong shown |", "|---|---|---|---|---|---|---|"]
    for name, rule in rules.items():
        for style in ["naskh", "thuluth", "diwani", "**all**"]:
            g = [lab for lab in labels if style == "**all**" or lab["style"] == style]
            preds = [(lab, rule(lab["file"])) for lab in g]
            shown = [(lab, p) for lab, p in preds if p]
            right = sum(is_correct(store, lab, p) for lab, p in shown)
            prec = f"{100 * right / len(shown):.0f}%" if shown else "–"
            lines.append(
                f"| {name} | {style} | {len(g)} | {100 * right / len(g):.1f}% | {100 * len(shown) / len(g):.0f}% | "
                f"{prec} | {100 * (len(shown) - right) / len(g):.1f}% |"
            )
    md = "\n".join(lines)
    Path(FIC / "recognition_agreement.md").write_text(md + "\n", encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
