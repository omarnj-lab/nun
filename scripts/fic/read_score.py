"""INTERNAL FIC test set, step 4: KhaṭṭVision v1 at 896² on every image, scored with verse_id_eval.py's logic.

Settings = the Quranic evaluation's 896² run (eval/notebooks/khattvision_quranic_eval.py, RES=896): notebook prompt,
chat template and greedy decoding, max area 896², max side 1792. One input difference, required by this source:
the originals are transparent PNGs with black ink over black transparent pixels, so each image is first composited
onto WHITE (the notebook's plain convert("RGB") would turn them into an all-black image).

Scoring (analysis/v1_verse_id/verse_id_eval.py): top-1 = primary(reading) shares an ayah text with the label's ayahs
(repeated verses count as correct); top-5 = top-1 or any of suggest(reading, 5).
Writes data/private/fic/readings.jsonl (resumable) and data/private/fic/v1_results.md.

    CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. python -m scripts.fic.read_score
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "analysis" / "v1_verse_id"))
import verse_id_eval as vid  # noqa: E402

FIC = Path("data/private/fic")
READINGS = FIC / "readings.jsonl"
RES = 896
Image.MAX_IMAGE_PIXELS = None  # trusted local originals, some > 600 MP


def flatten(path: Path) -> Image.Image:
    """Open, shrink to ≤ 4096 px (v1 sees ≤ 1792 anyway), composite transparency onto white."""
    im = Image.open(path)
    im.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        white = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(white, im)
    return im.convert("RGB")


def read_all(labels: list[dict]) -> dict[str, str]:
    done = {}
    if READINGS.exists():
        done = {r["file"]: r["reading"] for r in map(json.loads, READINGS.open(encoding="utf-8")) if not r["error"]}
    todo = [r for r in labels if r["file"] not in done]
    if todo:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from panels_read import load_predictor

        predict = load_predictor(RES * RES, 2 * RES)
        for r in todo:
            row = {"file": r["file"], "reading": None, "error": None}
            t = time.perf_counter()
            try:
                row["reading"] = predict(flatten(FIC / r["file"]))
            except Exception as e:  # noqa: BLE001
                row["error"] = f"{type(e).__name__}: {e}"
            row["seconds"] = round(time.perf_counter() - t, 1)
            with READINGS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if row["reading"] is not None:
                done[r["file"]] = row["reading"]
            print(
                f"{r['style']:<20} {Path(r['file']).name[:40]:<40} {row['seconds']:>5}s {row['error'] or ''}",
                flush=True,
            )
    return done


def gold_canon(r: dict) -> set[str]:
    s, a0, a1 = int(r["sura"]), int(r["aya_from"]), int(r["aya_to"])
    return {vid.ns(vid.norm(t, "drop")) for (ss, a, t) in vid.Q if ss == s and a0 <= a <= a1}


def score(labels: list[dict], readings: dict[str, str]) -> list[dict]:
    out = []
    for r in labels:
        reading = readings.get(r["file"])
        if reading is None:
            continue
        gold = gold_canon(r)
        p, _ = vid.primary(reading)
        top1 = bool(p and set(p["canon"]) & gold)
        top5 = top1 or any(set(x["canon"]) & gold for x in vid.suggest(reading, 5))
        answered = bool(p and p["score"] >= 90 and p["qlen"] >= 8)
        out.append(
            {
                **r,
                "reading": reading,
                "pred_ref": p["ref"] if p else "",
                "pred_score": p["score"] if p else 0,
                "top1": top1,
                "top5": top5,
                "answered90": answered,
            }
        )
    return out


def table(rows: list[dict]) -> list[str]:
    groups = defaultdict(list)
    for r in rows:
        groups[r["style"]].append(r)
    lines = [
        "| Style | n | Verse top-1 | Verse top-5 | Answered @ score ≥ 90 | Precision of those | Confidently wrong |",
        "|---|---|---|---|---|---|---|",
    ]

    def line(name: str, g: list[dict]) -> str:
        n = len(g)
        ans = [x for x in g if x["answered90"]]
        prec = f"{sum(x['top1'] for x in ans) / len(ans):.0%}" if ans else "–"
        wrong = sum(1 for x in ans if not x["top1"]) / n
        return (
            f"| {name} | {n} | {sum(x['top1'] for x in g) / n:.1%} | {sum(x['top5'] for x in g) / n:.1%} | "
            f"{len(ans) / n:.0%} | {prec} | {wrong:.1%} |"
        )

    for style in sorted(groups, key=lambda s: -len(groups[s])):
        lines.append(line(style, groups[style]))
    lines.append(line("**All**", rows))
    return lines


def main() -> None:
    labels = list(csv.DictReader((FIC / "labels.csv").open(encoding="utf-8")))
    readings = read_all(labels)
    rows = score(labels, readings)
    with (FIC / "v1_scores.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    failed = len(labels) - len(rows)
    md = [
        "# KhaṭṭVision v1 on the INTERNAL freeislamiccalligraphy.com test set",
        "",
        "**Internal testing only: these images must never be published (repo, app, Hugging Face, video, deck) or used "
        "to train a published model.**",
        "",
        f"- Images scored: {len(rows)} ({failed} not read). Labels: sura/ayah from each item's title, checked against "
        "the QuranEnc text (see labels.csv / label_failures.csv).",
        "- Model: `NAMAA-Space/KhattVision-Muse-Glimmer-30B-LoRA` @ 2cdaa0f, notebook prompt + chat template, greedy, "
        "max area 896², max side 1792 (same as the Quranic evaluation's 896² run).",
        "- Input difference: originals are transparent PNGs (black ink on black transparent pixels) → composited onto "
        "white before the notebook's resize.",
        "- Scoring: `analysis/v1_verse_id/verse_id_eval.py`: top-1 = `primary(reading)` shares an ayah text with the "
        "labelled ayahs (repeated verses count); top-5 = top-1 or any of `suggest(reading, 5)`. 'Answered' = primary "
        "match score ≥ 90 on ≥ 8 letters (as in FINDINGS.md); 'confidently wrong' is a share of all images.",
        "",
        *table(rows),
        "",
    ]
    (FIC / "v1_results.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
