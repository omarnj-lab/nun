"""Photo-matching test (PLAN_NOW, Oct 2–3 [PRE]): can a visitor's photo be matched to the right panel, and is an
unknown panel rejected?

Collection: data/panels/raw (Commons panels). Visitor photos: SIMULATED from each collection photo at three levels
(perspective, rotation, crop, wall around the panel, light, glare, blur, noise, JPEG); a stand-in until the team's
own repeat photos exist (put them in data/match_test/real_queries/<collection-file-stem>__anything.jpg and they are
scored too). Unknown panels (must be rejected): other Commons calligraphy (data/real/commons) and, internally only,
the FIC images (data/private/fic). Exact/near copies of a collection image (pHash ≤ 6) are removed from the
negatives. Writes eval/results/<date>/photo_matching/{results.md, results.json} (numbers only, no images).

    CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. python scripts/match_test.py
"""

from __future__ import annotations

import csv
import json
import random
import sys
import time
from datetime import date
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fic.read_score import flatten  # noqa: E402  (white background for transparent PNGs)

from nun.match.matcher import PanelMatcher  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
PANELS = Path("data/panels")
OUT = Path("eval/results") / date.today().isoformat() / "photo_matching"
EXAMPLES = Path("data/match_test/examples")
REAL_QUERIES = Path("data/match_test/real_queries")
SEED = 20261003
SAME_PANEL_INLIERS = 60  # collection photos verifying this strongly against each other show the same panel
LEVELS = {
    "easy": dict(
        persp=0.04, rot=4, pad=(0.05, 0.15), visible=0.95, bright=(0.85, 1.15), blur=0.6, glare=0.0, jpeg=(80, 90)
    ),
    "medium": dict(
        persp=0.09, rot=10, pad=(0.1, 0.35), visible=0.85, bright=(0.6, 1.3), blur=1.2, glare=0.3, jpeg=(60, 80)
    ),
    "hard": dict(
        persp=0.15, rot=15, pad=(0.2, 0.6), visible=0.70, bright=(0.4, 1.4), blur=2.2, glare=0.6, jpeg=(40, 65)
    ),
}


def load(path: Path, side: int = 1600) -> Image.Image:
    im = flatten(path) if path.suffix.lower() == ".png" else Image.open(path).convert("RGB")
    im.thumbnail((side, side), Image.Resampling.LANCZOS)
    return im


def augment(img: Image.Image, level: str, rng: random.Random) -> Image.Image:
    """Simulated phone photo of a flat panel hanging on a wall."""
    p = LEVELS[level]
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w = a.shape[:2]
    pad = rng.uniform(*p["pad"])
    H, W = int(h * (1 + 2 * pad)), int(w * (1 + 2 * pad))
    wall = np.full((H, W, 3), [rng.uniform(90, 230) for _ in range(3)], np.float32)
    noise = np.random.default_rng(rng.randint(0, 9999)).normal(0, 18, (H, W)).astype(np.float32)
    wall += cv2.GaussianBlur(noise, (0, 0), 3)[..., None]
    # panel corners: perspective jitter + rotation around the centre
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    j = p["persp"] * max(w, h)
    dst = np.float32([[x + (W - w) / 2 + rng.uniform(-j, j), y + (H - h) / 2 + rng.uniform(-j, j)] for x, y in src])
    ang = np.deg2rad(rng.uniform(-p["rot"], p["rot"]))
    c = dst.mean(0)
    R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]], np.float32)
    dst = (dst - c) @ R.T + c
    M = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
    warped = cv2.warpPerspective(a, M, (W, H), flags=cv2.INTER_LINEAR)
    mask = cv2.warpPerspective(np.ones((h, w), np.float32), M, (W, H))[..., None]
    photo = warped * mask + wall * (1 - mask)
    # frame the shot: keep ≥ `visible` of the panel's bounding box, possibly cutting an edge
    x0, y0 = dst.min(0)
    x1, y1 = dst.max(0)
    bw, bh = x1 - x0, y1 - y0
    cut = 1 - p["visible"]
    cx0 = max(0, int(x0 - rng.uniform(0, pad) * w + rng.uniform(0, cut) * bw * (rng.random() < 0.5)))
    cy0 = max(0, int(y0 - rng.uniform(0, pad) * h + rng.uniform(0, cut) * bh * (rng.random() < 0.5)))
    cx1 = min(W, int(x1 + rng.uniform(0, pad) * w - rng.uniform(0, cut) * bw * (rng.random() < 0.5)))
    cy1 = min(H, int(y1 + rng.uniform(0, pad) * h - rng.uniform(0, cut) * bh * (rng.random() < 0.5)))
    photo = photo[cy0:cy1, cx0:cx1]
    # light: brightness, contrast, colour cast; glare spot
    photo = (photo - 128) * rng.uniform(0.75, 1.15) + 128
    photo = photo * rng.uniform(*p["bright"]) * np.array([rng.uniform(0.9, 1.1) for _ in range(3)], np.float32)
    if rng.random() < p["glare"]:
        hh, ww = photo.shape[:2]
        yy, xx = np.mgrid[0:hh, 0:ww]
        r = rng.uniform(0.1, 0.3) * max(hh, ww)
        spot = np.exp(-(((xx - rng.uniform(0, ww)) ** 2 + (yy - rng.uniform(0, hh)) ** 2) / (2 * r * r)))
        photo = photo + spot[..., None] * rng.uniform(80, 200)
    sigma = rng.uniform(0, p["blur"])
    if sigma > 0.3:
        photo = cv2.GaussianBlur(photo, (0, 0), sigma)
    photo += np.random.default_rng(rng.randint(0, 9999)).normal(0, rng.uniform(0, 6), photo.shape)
    out = Image.fromarray(np.clip(photo, 0, 255).astype(np.uint8))
    out.thumbnail((rng.randint(900, 1600),) * 2, Image.Resampling.LANCZOS)
    buf = cv2.imencode(
        ".jpg", cv2.cvtColor(np.asarray(out), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, rng.randint(*p["jpeg"])]
    )[1]
    return Image.fromarray(cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB))


def main() -> None:
    rng = random.Random(SEED)
    gallery = [r["file"] for r in csv.DictReader((PANELS / "candidates.csv").open(encoding="utf-8"))]
    t0 = time.perf_counter()
    m = PanelMatcher(min_inliers=0)  # threshold is chosen below from the negatives
    gal_imgs = {f: load(PANELS / "raw" / f) for f in gallery}
    m.add_many([(f, im, None) for f, im in gal_imgs.items()])
    build_s = time.perf_counter() - t0
    gal_hash = {f: imagehash.phash(im) for f, im in gal_imgs.items()}

    # collection photos that show the same physical panel (other photo, crop, resize) form one group: matching any
    # photo of the group is correct. Two photos are grouped when they verify against each other strongly.
    parent = {f: f for f in gallery}

    def find(f: str) -> str:
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    for f in gallery:
        for cid, inl, _, cov in m.match(gal_imgs[f]).candidates:
            if cid != f and inl >= SAME_PANEL_INLIERS and cov >= 0.5:  # must also agree across the text
                parent[find(cid)] = find(f)
    group = {f: find(f) for f in gallery}

    queries = []  # (expected collection id, level, image)
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(gallery):
        for level in LEVELS:
            q = augment(gal_imgs[f], level, rng)
            queries.append((f, level, q))
            if i < 4:
                q.save(EXAMPLES / f"{Path(f).stem[:10]}_{level}.jpg", quality=85)
    stems = {Path(f).stem: f for f in gallery}
    if REAL_QUERIES.exists():
        for p in sorted(REAL_QUERIES.glob("*.*")):
            if p.stem.split("__")[0] in stems:
                queries.append((stems[p.stem.split("__")[0]], "real", load(p)))

    negatives, dropped = [], 0  # (source, path, image)
    neg_paths = [("commons", p) for p in sorted(Path("data/real/commons/images").glob("*.*"))]
    neg_paths += [("fic", p) for p in sorted(Path("data/private/fic/images").glob("*/*.*"))]
    for src, p in neg_paths:
        try:
            im = load(p)
        except Exception:  # noqa: BLE001
            continue
        h = imagehash.phash(im)
        if min(h - g for g in gal_hash.values()) <= 6:
            dropped += 1  # the same image is in the collection: not a negative
            continue
        negatives.append((src, p, im))

    def run(img: Image.Image) -> tuple[object, float]:
        t = time.perf_counter()
        r = m.match(img)
        return r, time.perf_counter() - t

    q_res = [(exp, lvl, *run(img)) for exp, lvl, img in queries]
    n_res = [(src, *run(img)) for src, _, img in negatives]
    with (Path("data/match_test") / "details.jsonl").open("w", encoding="utf-8") as f:
        for exp, lvl, r, _t in q_res:
            row = {
                "kind": "query",
                "expected": exp,
                "expected_group": group[exp],
                "level": lvl,
                "best": r.id,
                "best_group": group[r.id],
                "inliers": r.inliers,
                "coverage": round(r.coverage, 3),
                "cosine": round(r.cosine, 3),
            }
            f.write(json.dumps(row) + "\n")
        for (src, p, _), (_, r, _t) in zip(negatives, n_res, strict=True):
            row = {
                "kind": "negative",
                "source": src,
                "path": str(p),
                "best": r.id,
                "inliers": r.inliers,
                "coverage": round(r.coverage, 3),
                "cosine": round(r.cosine, 3),
            }
            f.write(json.dumps(row) + "\n")

    # thresholds: accept when inliers ≥ T AND centre coverage ≥ C; sweep both
    max_neg = max((r.inliers for _, r, _ in n_res), default=0)
    sweep = []
    for T in (15, 20, 30, 40, 60):
        for C in (0.0, 0.25, 0.4, 0.5, 0.6, 0.75):

            def ok(r, T=T, C=C) -> bool:
                return r.inliers >= T and r.coverage >= C

            fa = sum(ok(r) for _, r, _ in n_res)
            row = {"inliers_min": T, "coverage_min": C, "false_accepts": fa}
            for lvl in [*LEVELS, "real"]:
                sel = [(e, r) for e, lv, r, _ in q_res if lv == lvl]
                if sel:
                    row[f"correct_{lvl}"] = round(sum(ok(r) and group[r.id] == group[e] for e, r in sel) / len(sel), 4)
                    row[f"wrong_{lvl}"] = sum(ok(r) and group[r.id] != group[e] for e, r in sel)
            sweep.append(row)
    zero_fa = [r for r in sweep if r["false_accepts"] == 0]
    chosen = max(zero_fa, key=lambda r: (r["correct_hard"], r["correct_medium"]), default=None)
    emb_top1 = {
        lvl: round(
            np.mean(
                [r.candidates and max(r.candidates, key=lambda c: c[2])[0] == e for e, lv, r, _ in q_res if lv == lvl]
            ),
            4,
        )
        for lvl in LEVELS
    }
    lat = sorted(t for *_, t in q_res + n_res)
    summary = {
        "collection": len(gallery),
        "queries": {lvl: sum(1 for _, lv, *_ in q_res if lv == lvl) for lvl in [*LEVELS, "real"]},
        "negatives": {
            "commons": sum(s == "commons" for s, *_ in n_res),
            "fic_internal": sum(s == "fic" for s, *_ in n_res),
        },
        "negatives_dropped_as_same_image": dropped,
        "max_inliers_on_a_negative": max_neg,
        "chosen_thresholds_zero_false_accepts": chosen,
        "embedding_only_top1": emb_top1,
        "sweep": sweep,
        "latency_s": {"p50": round(lat[len(lat) // 2], 3), "p95": round(lat[int(len(lat) * 0.95)], 3)},
        "index_build_s": round(build_s, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    cols = (
        ["inliers_min", "coverage_min", "false_accepts"]
        + [f"correct_{lv}" for lv in LEVELS]
        + [f"wrong_{lv}" for lv in LEVELS]
    )
    if summary["queries"]["real"]:
        cols += ["correct_real", "wrong_real"]
    md = [
        "# Photo-matching test",
        "",
        "```json",
        json.dumps({k: v for k, v in summary.items() if k != "sweep"}, indent=2),
        "```",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "---|" * len(cols),
    ]
    md += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in sweep]
    (OUT / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
