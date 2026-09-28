"""Compile reviewed test set B labels (Commons photos) → eval/sets/real-test.jsonl (SPEC §10 format) + leakage check.

Only labels CONFIRMED by a person other than the labeller are included; "skip" labels are dropped. Labels proposed
by Claude and confirmed by a person are marked model_assisted (disclosed with the results). Every included image is
perceptual-hashed against all DuwatBench (training) images and, when present, data/synth images: any pair within
Hamming distance ≤ 4 is excluded and reported (the real-test set must never overlap training data).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import imagehash
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from label_tool.app import candidates, image_id, image_path, state  # noqa: E402

OUT = Path("eval/sets/real-test.jsonl")
REPORT = Path("eval/sets/real-test.report.json")
MAX_HAMMING = 4


def training_hashes() -> list[tuple[str, imagehash.ImageHash]]:
    from datasets import load_dataset

    out = []
    for row in load_dataset("MBZUAI/DuwatBench", split="train"):
        out.append((f"duwatbench:{row['image_id']}", imagehash.phash(row["image"].convert("RGB"))))
    synth = Path("data/synth/images")
    if synth.exists():
        out += [(f"synth:{p.name}", imagehash.phash(Image.open(p).convert("RGB"))) for p in synth.glob("*.*")]
    return out


def main() -> None:
    st = state()
    by_id = {image_id(c): c for c in candidates("commons")}
    rows = []
    for cid, s in st.items():
        lab, rev = s.get("label"), s.get("review")
        if cid not in by_id or not lab or not rev or rev["verdict"] != "confirm" or lab["gt_type"] == "skip":
            continue
        c = by_id[cid]
        rows.append(
            {
                "id": cid,
                "file": str(image_path(c)),
                "model_assisted": lab["labeller"].startswith("claude"),
                "source_url": c["source_url"],
                "license": c["license"],
                "license_url": c.get("license_url"),
                "author": c.get("author") or c.get("credit"),
                "gt_type": lab["gt_type"],
                "refs": lab["refs"],
                "list_ids": lab["list_ids"],
                "gt_text": lab["gt_text"],
                "style": lab["style"],
                "theme": lab["theme"],
                "labelled_by": lab["labeller"],
                "reviewed_by": rev["reviewer"],
            }
        )
    train = training_hashes()
    leaks = []
    for r in rows:
        h = imagehash.phash(Image.open(r["file"]).convert("RGB"))
        near = [(name, h - th) for name, th in train if h - th <= MAX_HAMMING]
        if near:
            leaks.append({"id": r["id"], "matches": near[:3]})
    leaked = {x["id"] for x in leaks}
    kept = [r for r in rows if r["id"] not in leaked]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
    mix = Counter(r["gt_type"] for r in kept)
    n = max(len(kept), 1)
    report = {
        "images": len(kept),
        "excluded_near_duplicates_of_training": leaks,
        "mix": dict(mix),
        "mix_share": {k: round(v / n, 2) for k, v in mix.items()},
        "target_share": {"quran": 0.60, "name+dhikr": 0.15, "other": 0.25},
        "licenses": dict(Counter(r["license"] for r in kept)),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({k: v for k, v in report.items() if k != "excluded_near_duplicates_of_training"}, ensure_ascii=False)
    )
    print(f"excluded as near-duplicates of training images: {len(leaks)}")


if __name__ == "__main__":
    main()
