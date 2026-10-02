"""Inspect 'negatives' that the matcher accepted: same panel (another photo/crop) or a real false match?

Writes side-by-side sheets (left: the 'unknown' image, right: the collection photo it matched) to
data/match_test/negatives_check/ for a human look, and prints the inlier distribution by source.
"""

import collections
import json
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
OUT = Path("data/match_test/negatives_check")
rows = [json.loads(line) for line in open("data/match_test/details.jsonl", encoding="utf-8")]
neg = sorted((r for r in rows if r["kind"] == "negative"), key=lambda r: -r["inliers"])
print("negatives:", len(neg), dict(collections.Counter(r["source"] for r in neg)))
for lo, hi in [(30, 60), (60, 100), (100, 300), (300, 10**6)]:
    sel = [r for r in neg if lo <= r["inliers"] < hi]
    print(f"  inliers {lo}-{hi}: {len(sel)} {dict(collections.Counter(r['source'] for r in sel))}")
hard = sorted(r["inliers"] for r in rows if r["kind"] == "query" and r["level"] == "hard")
print(
    "hard simulated photos: inliers min", hard[0], "· 5th pct", hard[len(hard) // 20], "· median", hard[len(hard) // 2]
)

OUT.mkdir(parents=True, exist_ok=True)
for old in OUT.glob("*.jpg"):
    old.unlink()
pick = [r for r in neg if r["inliers"] >= 15 and r.get("coverage", 0) >= 0.4]  # what still gets through
for i, r in enumerate(pick):
    a = Image.open(r["path"]).convert("RGB")
    b = Image.open(Path("data/panels/raw") / r["best"]).convert("RGB")
    for im in (a, b):
        im.thumbnail((420, 420))
    sheet = Image.new("RGB", (860, 440), "white")
    sheet.paste(a, (0, 0))
    sheet.paste(b, (440, 0))
    name = f"{i:02d}_{r['source']}_{r['inliers']}.jpg"
    sheet.save(OUT / name, quality=80)
    print(
        name, "coverage", r.get("coverage"), "cosine", r["cosine"], "|", Path(r["path"]).name[:40], "->", r["best"][:16]
    )
