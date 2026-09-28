"""Evaluation sets. Each item: ground-truth row (eval.metrics format) + a way to load its image.

duwat-heldout: v1's fixed 50 held-out DuwatBench rows (model card). Ground truth is derived AUTOMATICALLY from
DuwatBench's gold text (corpus location / list match) and is not human-reviewed: use it for v1 comparability and
harness checks, and real-test for the headline numbers.
real-test:     eval/sets/real-test.jsonl, compiled from reviewed labels (M3).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from functools import lru_cache
from pathlib import Path

from PIL import Image

from nun.corpus.fragment import QuranIndex, locate_fuzzy
from nun.corpus.store import CorpusStore
from nun.normalize.arabic import normalize, normalize_ns

DUWAT_HELDOUT_ROWS = [
    212, 79, 565, 832, 467, 837, 186, 239, 83, 777, 449, 475, 270, 841, 808, 93, 408, 92, 1255, 396,
    1264, 282, 220, 235, 842, 835, 854, 184, 441, 662, 847, 225, 113, 1211, 63, 1225, 571, 292, 533, 84,
    1259, 274, 540, 773, 848, 190, 104, 1256, 810, 706,
]  # fmt: skip
LISTS = Path("data/lists")


@lru_cache
def _index() -> QuranIndex:
    return QuranIndex(CorpusStore())


def _list(kind: str) -> list[dict]:
    p = LISTS / f"{kind}.draft.jsonl"
    return [json.loads(line) for line in p.open(encoding="utf-8")] if p.exists() else []


def auto_ground_truth(text: str, category: str) -> dict:
    """Ground truth from gold text: quran (exact, all occurrences; else fuzzy ≥ 90) → name → dhikr → other."""
    idx, q_ns, q_norm = _index(), normalize_ns(text), normalize(text)
    if category in ("quranic", "devotional invocation") and len(q_ns) >= 2:
        hits = idx.find_exact(q_ns) or (idx.find_exact(q_ns, whole_words=False) if len(q_ns) >= 8 else [])
        spans = [idx.span(*h) for h in hits]
        spans = [s for s in spans if not s["cross_sura"]]
        if not spans and len(q_ns) >= 8 and (got := locate_fuzzy(idx, q_ns)) and got[1] >= 90:
            spans = [got[0]]
        if spans:
            refs = [{k: s[k] for k in ("sura", "aya_from", "aya_to")} for s in spans]
            return {"gt_type": "quran", "refs": refs, "list_ids": []}
    names = [n["id"] for n in _list("names") if n["text_norm"] == q_norm]
    if names:
        return {"gt_type": "name", "refs": [], "list_ids": names}
    dhikr = [d["id"] for d in _list("dhikr") if d["text_norm"] == q_norm]
    if dhikr:
        return {"gt_type": "dhikr", "refs": [], "list_ids": dhikr}
    return {"gt_type": "other", "refs": [], "list_ids": []}


def load(name: str, limit: int | None = None) -> Iterator[tuple[dict, Callable[[], Image.Image]]]:
    if name == "duwat-heldout":
        from datasets import load_dataset

        ds = load_dataset("MBZUAI/DuwatBench", split="train")
        for row_index in DUWAT_HELDOUT_ROWS[:limit]:
            s = ds[row_index]
            text = " ".join(s["text"])
            gt = {
                "id": f"duwat-{row_index}",
                "gt_text": text,
                "style": s["style"],
                "theme": s["category"],
                "labels": "auto-from-duwatbench-gold",
                **auto_ground_truth(text, s["category"]),
            }
            yield gt, (lambda s=s: s["image"].convert("RGB"))
    elif name == "real-test":
        rows = [json.loads(line) for line in Path("eval/sets/real-test.jsonl").open(encoding="utf-8")]
        for gt in rows[:limit]:
            yield gt, (lambda p=gt["file"]: Image.open(p).convert("RGB"))
    else:
        raise ValueError(f"unknown set {name}")
