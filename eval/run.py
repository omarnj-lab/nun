"""Run a system on an eval set → eval/results/<date>/<set>__<system>/{predictions.jsonl, metrics.json, coverage.json}.

    python -m eval.run --set duwat-heldout --system v1-locate [--limit 5]

Results hold text only (readings, refs, metrics), never images.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from eval import sets
from eval.metrics import compute, coverage_curve
from eval.systems import SYSTEMS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["duwat-heldout", "real-test"])
    ap.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", type=Path, default=Path("eval/results"))
    args = ap.parse_args()

    system = SYSTEMS[args.system]()
    gts, preds = [], []
    for gt, image in sets.load(args.set, args.limit):
        pred = system(gt, image)
        gts.append(gt)
        preds.append(pred)
        answer = pred.get("refs") or pred.get("list_ids") or ""
        print(f"{gt['id']:<14} gt={gt['gt_type']:<6} → {pred['status']:<10} {answer}")

    metrics = compute(gts, preds) | {"set": args.set, "system": args.system, "limit": args.limit}
    name = f"{args.set}__{args.system}" + ("" if args.limit is None else f"__n{args.limit}")
    run_dir = args.out / date.today().isoformat() / name
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = [{"gt": g, "pred": p} for g, p in zip(gts, preds, strict=True)]
    (run_dir / "predictions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    (run_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "coverage.json").write_text(json.dumps(coverage_curve(gts, preds), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in metrics.items() if k != "confident_errors"}, ensure_ascii=False))
    print(f"→ {run_dir}")


if __name__ == "__main__":
    main()
