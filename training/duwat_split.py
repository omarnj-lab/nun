"""DuwatBench split for Nūn: train / validation (calibration dev) / test (= test set A, never trained on).

Uses KhaṭṭVision v1's grouping (notebook cell 12: normalised full text, source URL, pHash ≤ 4) so near-duplicates
never straddle splits. v1's exact split (seed 3909) could NOT be reproduced on the current dataset/library
versions (no seed of 5,000 puts all 50 of v1's known held-out rows in test; best 34/50), so the split is built
around the one certain fact: the 50 rows on v1's model card were never trained on by v1.
  - test: the groups of those 50 rows, then random whole groups (seed 3909) up to ≥ 180 rows
  - validation: random whole groups up to ≥ 180 rows (for gate calibration in M9, never real-test)
  - train: everything else (M7/M8 training uses only these)
v1-vs-v2 comparisons use only the 50 known rows (eval set duwat-heldout); other systems use all of test.

    python -m training.duwat_split   → eval/sets/duwatbench_split.json (row indices only)
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import imagehash
import numpy as np
from datasets import load_dataset

from eval.sets import DUWAT_HELDOUT_ROWS

SEED = 3909  # v1's selected split seed, reused for our group sampling
TARGET = 180  # rows per held-out split (v1: test 180)
MAX_GROUP = 20  # very large groups (shared source URL) go to train, so one group cannot dominate a split
OUT = Path("eval/sets/duwatbench_split.json")
_DIACRITICS = re.compile("[ً-ٰٟۖ-ۭ]")


def normalize_arabic(text: str) -> str:  # notebook cell 12, verbatim logic
    text = unicodedata.normalize("NFKC", str(text))
    text = _DIACRITICS.sub("", text)
    text = re.sub("[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"[^؀-ۿ0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent, self.rank = list(range(n)), [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def groups_for(ds) -> np.ndarray:
    n = len(ds)
    uf = UnionFind(n)
    first_text, first_src = {}, {}
    for i in range(n):
        key = " || ".join(sorted(normalize_arabic(t) for t in ds[i]["text"]))
        if key in first_text:
            uf.union(i, first_text[key])
        else:
            first_text[key] = i
        src = str(ds[i].get("source") or "").strip()
        if src.startswith(("http://", "https://")):
            if src in first_src:
                uf.union(i, first_src[src])
            else:
                first_src[src] = i
    ph = [imagehash.phash(ds[i]["image"].convert("RGB"), hash_size=8) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if ph[i] - ph[j] <= 4:
                uf.union(i, j)
    return np.array([uf.find(i) for i in range(n)])


def take_groups(order: list[int], sizes: dict[int, int], start: set[int], target: int) -> set[int]:
    chosen, total = set(start), sum(sizes[g] for g in start)
    for g in order:
        if total >= target:
            break
        if g not in chosen and sizes[g] <= MAX_GROUP:
            chosen.add(g)
            total += sizes[g]
    return chosen


def main() -> None:
    ds = load_dataset("MBZUAI/DuwatBench", split="train")
    groups = groups_for(ds)
    sizes = {int(g): int((groups == g).sum()) for g in set(groups.tolist())}
    order = [int(g) for g in np.random.default_rng(SEED).permutation(sorted(sizes))]
    known = {int(groups[r]) for r in DUWAT_HELDOUT_ROWS}
    test_g = take_groups(order, sizes, known, TARGET)
    val_g = take_groups([g for g in order if g not in test_g], sizes, set(), TARGET)
    split = {"train": [], "validation": [], "test": []}
    for i, g in enumerate(groups.tolist()):
        split["test" if g in test_g else "validation" if g in val_g else "train"].append(i)
    assert set(DUWAT_HELDOUT_ROWS) <= set(split["test"])
    for a, b in [("train", "validation"), ("train", "test"), ("validation", "test")]:
        assert not {groups[i] for i in split[a]} & {groups[i] for i in split[b]}, f"group leakage {a}/{b}"
    cats = {k: dict(sorted(Counter(ds[i]["category"] for i in v).items())) for k, v in split.items()}
    OUT.write_text(
        json.dumps(
            {
                "method": "v1 grouping; test = groups of v1's 50 known held-out rows + random groups (seed 3909)",
                "sizes": {k: len(v) for k, v in split.items()},
                "groups": len(sizes),
                "categories": cats,
                "v1_known_heldout_rows": DUWAT_HELDOUT_ROWS,
                **split,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print("sizes:", {k: len(v) for k, v in split.items()}, "· groups:", len(sizes))
    print("test categories:", cats["test"])
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
