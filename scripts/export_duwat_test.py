"""Test set A → labelling tool: export the DuwatBench held-out test images + automatic labels for spot-checking.

Images go to data/real/duwat_test/ (gitignored: DuwatBench images are never redistributed). Each gets a label
event from DuwatBench's own gold annotation (text, style, category), with the Quran reference found by corpus
lookup (eval.sets.auto_ground_truth), labeller "auto:duwatbench-gold". People spot-check them in Review mode
(set selector "Set A"); a rejection sends the image back for a human label.

    PYTHONPATH=. python scripts/export_duwat_test.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).parent))
from label_tool.app import SOURCES, STYLES, append, state  # noqa: E402

from eval.sets import auto_ground_truth  # noqa: E402

SPLIT = Path("eval/sets/duwatbench_split.json")
LABELLER = "auto:duwatbench-gold"


def main() -> None:
    root = SOURCES["duwat"]
    (root / "images").mkdir(parents=True, exist_ok=True)
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    ds = load_dataset("MBZUAI/DuwatBench", split="train")
    st = state()
    rows, new_labels = [], 0
    for r in split["test"]:
        s = ds[r]
        cid = f"duwat-{r}"
        dest = root / "images" / f"{cid}.jpg"
        if not dest.exists():
            s["image"].convert("RGB").save(dest, "JPEG", quality=92)
        rows.append(
            {
                "id": cid,
                "title": f"DuwatBench row {r} ({s['image_id']})",
                "file": f"images/{cid}.jpg",
                "source_url": "https://huggingface.co/datasets/MBZUAI/DuwatBench",
                "license": "DuwatBench (evaluation only; not redistributed)",
                "author": None,
                "category": s["category"],
                "pool": "duwat-test",
                "width": s["image"].width,
                "height": s["image"].height,
            }
        )
        text = " ".join(s["text"])
        styles = [x for x in re.split(r"\s*,\s*", s["style"].strip()) if x in STYLES]
        label = {
            "event": "label",
            "id": cid,
            "labeller": LABELLER,
            **auto_ground_truth(text, s["category"]),
            "gt_text": text,
            "style": styles,
            "theme": s["category"],
            "notes": "auto: DuwatBench annotators' text/style/category; Quran reference by corpus lookup",
        }
        prev = st.get(cid, {})
        if prev:
            # refresh only an automatic label nobody has reviewed yet, and only if it changed; never touch human work
            old = prev.get("label", {})
            keys = ("gt_type", "refs", "list_ids", "style", "theme")
            if old.get("labeller") != LABELLER or "review" in prev or all(old.get(k) == label[k] for k in keys):
                continue
        append(label)
        new_labels += 1
    (root / "candidates.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8"
    )
    print(f"set A: {len(rows)} images exported, {new_labels} automatic labels added")


if __name__ == "__main__":
    main()
