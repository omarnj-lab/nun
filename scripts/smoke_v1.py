"""M0 smoke test: KhaṭṭVision v1 on 3 held-out DuwatBench images with the notebook's exact prompts.

Writes data/smoke/v1_smoke.json. Run: make smoke-v1
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
from datasets import load_dataset

from nun.vlm.khatt_v1 import ADAPTER, BASE_MODEL, KhattV1

ROWS = [212, 79, 565]  # first 3 of v1's fixed 50-image held-out evaluation rows (model card)
OUT = Path("data/smoke/v1_smoke.json")


def main() -> None:
    v1 = KhattV1()
    mem_after_load = torch.cuda.max_memory_allocated(0) / 2**30
    print(f"loaded in {v1.load_seconds:.0f}s, {mem_after_load:.1f} GiB allocated")
    ds = load_dataset("MBZUAI/DuwatBench", split="train")
    results = []
    for idx in ROWS:
        s = ds[idx]
        ocr, ocr_s = v1.read(s["image"])
        parsed, raw, st_s = v1.structure(s["image"])
        valid = isinstance(parsed, dict) and {"styles", "theme", "regions"} <= parsed.keys()
        results.append(
            {
                "row_index": idx,
                "image_id": s["image_id"],
                "gold_text": "\n".join(s["text"]),
                "gold_style": s["style"],
                "gold_theme": s["category"],
                "ocr": ocr,
                "ocr_seconds": round(ocr_s, 2),
                "structured_raw": raw,
                "structured_json_valid": valid,
                "structured_seconds": round(st_s, 2),
            }
        )
        print(f"row {idx}: json_valid={valid} ocr={ocr_s:.1f}s structured={st_s:.1f}s")
    summary = {
        "base": BASE_MODEL,
        "adapter": ADAPTER,
        "gpu": torch.cuda.get_device_name(0),
        "load_seconds": round(v1.load_seconds, 1),
        "mem_after_load_gib": round(mem_after_load, 2),
        "peak_mem_gib": round(torch.cuda.max_memory_allocated(0) / 2**30, 2),
        "json_valid": f"{sum(r['structured_json_valid'] for r in results)}/{len(results)}",
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
