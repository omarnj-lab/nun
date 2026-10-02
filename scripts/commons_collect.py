"""M3: collect candidate real-world calligraphy photos from Wikimedia Commons for the `real-test` set.

Walks the categories in SOURCES.md §5 (+ subcategories to --depth), keeps only files whose license is
CC0 / Public domain / CC BY / CC BY-SA (no NC/ND/GFDL-only/fair use), and saves a ≤1600 px rendition plus
metadata (license, author, credit, source URL, sha1) to data/real/commons/. Candidates are then labelled
with the labelling tool; unlabelled or "other/unreadable" images are simply not used.

Usage: python scripts/commons_collect.py [--max 600] [--depth 2]
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = "NunCommonsCollector/0.2 (Islamic-content AI challenge: evaluation set and demo calligraphy panels; https://huggingface.co/NAMAA-Space)"
CATEGORIES = [
    "Islamic calligraphy",
    "Thuluth inscriptions",
    "Thuluth style",
    "Allah in calligraphy",
    "﷽",
    "Arabic calligraphy",
    "Calligraphy of the Ottoman Empire",
    "Naskh (script)",
    "Nastaliq",
    "Calligraphy of Muhammad",
]
# Test set B: categories verified (2026-09-28, scripts/commons_probe.py) to hold real inscriptions, most likely Quranic.
# Commons has no "Quranic inscriptions" category; these are the closest that exist.
TARGETED = ["Basmala", "Thuluth inscriptions", "Mihrabs", "Arabic inscriptions", "Shahada"]
OUT = Path("data/real/commons")
ALLOWED = re.compile(r"^(cc0|cc[- ]zero|public domain|pd\b|pd-|cc[- ]by(-sa)?([- ][0-9.,]+)?( [a-z-]+)?$)", re.I)
REJECT = re.compile(r"\b(nc|nd|non-?commercial|no ?deriv|fair use)\b", re.I)
MIN_SIDE = 400


def api(**params) -> dict:
    params |= {"format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"API failed: {url}")


def members(category: str, cmtype: str) -> list[str]:
    out, cont = [], {}
    while True:
        d = api(
            action="query", list="categorymembers", cmtitle=f"Category:{category}", cmtype=cmtype, cmlimit="500", **cont
        )
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" not in d:
            return out
        cont = {"cmcontinue": d["continue"]["cmcontinue"]}


def walk(roots: list[str], depth: int) -> dict[str, str]:
    """file title → the category it was found in."""
    seen_cats, files = set(), {}
    frontier = [(c, 0) for c in roots]
    while frontier:
        cat, d = frontier.pop(0)
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        for f in members(cat, "file"):
            files.setdefault(f, cat)
        if d < depth:
            frontier += [(s.removeprefix("Category:"), d + 1) for s in members(cat, "subcat")]
    print(f"walked {len(seen_cats)} categories → {len(files)} files")
    return files


def strip_html(s: str | None) -> str | None:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip() if s else None


def license_ok(short: str | None) -> bool:
    return bool(short) and bool(ALLOWED.match(short.strip())) and not REJECT.search(short)


def download(titles: list[str], cat_of: dict[str, str], pool: str, budget: int, meta, rejected: dict) -> int:
    """Fetch metadata for `titles` in batches of 50; keep license-OK images until `budget` is reached."""
    kept = 0
    for i in range(0, len(titles), 50):
        if kept >= budget:
            break
        d = api(
            action="query",
            titles="|".join(titles[i : i + 50]),
            prop="imageinfo",
            iiprop="url|extmetadata|sha1|size|mime",
            iiurlwidth="1600",
        )
        for page in d.get("query", {}).get("pages", []):
            if kept >= budget:
                break
            info = (page.get("imageinfo") or [None])[0]
            if not info:
                continue
            em = {k: v.get("value") for k, v in (info.get("extmetadata") or {}).items()}
            lic = strip_html(em.get("LicenseShortName"))
            if not license_ok(lic):
                rejected["license"] += 1
                continue
            if info.get("mime") not in ("image/jpeg", "image/png"):
                rejected["mime"] += 1
                continue
            if min(info.get("width", 0), info.get("height", 0)) < MIN_SIDE:
                rejected["size"] += 1
                continue
            ext = ".png" if info["mime"] == "image/png" else ".jpg"
            dest = OUT / "images" / f"{info['sha1']}{ext}"
            if not dest.exists():
                req = urllib.request.Request(info.get("thumburl") or info["url"], headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=120) as r:
                    dest.write_bytes(r.read())
                time.sleep(0.5)
            row = {
                "title": page["title"],
                "file": str(dest.relative_to(OUT)),
                "sha1_original": info["sha1"],
                "source_url": info["descriptionurl"],
                "license": lic,
                "license_url": em.get("LicenseUrl"),
                "author": strip_html(em.get("Artist")),
                "credit": strip_html(em.get("Credit")),
                "attribution_required": em.get("AttributionRequired"),
                "category": cat_of[page["title"]],
                "pool": pool,
                "width": info["width"],
                "height": info["height"],
            }
            meta.write(json.dumps(row, ensure_ascii=False) + "\n")
            meta.flush()
            kept += 1
    return kept


# ---- demo panel collection (data/panels/): candidates for the human-confirmed panel set ----
PANEL_CATEGORIES = [
    "Thuluth inscriptions",
    "Thuluth style",
    "Allah in calligraphy",
    "﷽",
    "Arabic calligraphy",
    "Calligraphy of the Ottoman Empire",
    "Naskh (script)",
    "Islamic calligraphy",
]
PANELS = Path("data/panels")
PANEL_MIN_WIDTH = 800
PANEL_FIELDS = ["file", "title", "url", "license", "author", "credit", "category", "width", "height"]
# Not a panel or inscription: manuscripts and other objects (checked on the title and the file description)
NOT_PANEL = re.compile(
    r"manuscript|folio|codex|\bpages?\b|\bleaf\b|\bleaves\b|\bbook|binding|\bcoins?\b|dinar|dirham|stamp|banknote|"
    r"\bmaps?\b|\bflag|\bfont|typeface|alphabet|\blogo|poster|diagram|\bletter\b|document|\bms\.?\s?\d|"
    r"مخطوط|مصحف|عملة|طابع",
    re.I,
)


def panels(target: int, depth: int) -> None:
    raw = PANELS / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    csv_path = PANELS / "candidates.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8"))) if csv_path.exists() else []
    seen = {r["title"] for r in rows}
    rejected = {"license": 0, "format": 0, "width": 0, "not_panel": 0}
    per_cat = -(-target // len(PANEL_CATEGORIES))  # even share first, then a second pass fills up to target
    walked = {cat: walk([cat], depth) for cat in PANEL_CATEGORIES}
    for quota in (per_cat, target):
        for cat in PANEL_CATEGORIES:
            titles = [t for t in walked[cat] if t not in seen]
            taken = sum(1 for r in rows if r["category"] == cat)
            for i in range(0, len(titles), 50):
                if taken >= quota or len(rows) >= target:
                    break
                d = api(
                    action="query",
                    titles="|".join(titles[i : i + 50]),
                    prop="imageinfo",
                    iiprop="url|extmetadata|sha1|size|mime",
                    iiurlwidth="2048",
                )
                for page in d.get("query", {}).get("pages", []):
                    if taken >= quota or len(rows) >= target:
                        break
                    seen.add(page["title"])
                    info = (page.get("imageinfo") or [None])[0]
                    if not info:
                        continue
                    em = {k: v.get("value") for k, v in (info.get("extmetadata") or {}).items()}
                    lic = strip_html(em.get("LicenseShortName"))
                    desc = strip_html(em.get("ImageDescription")) or ""
                    if not license_ok(lic):
                        rejected["license"] += 1
                    elif info.get("mime") not in ("image/jpeg", "image/png"):
                        rejected["format"] += 1
                    elif info.get("width", 0) < PANEL_MIN_WIDTH:
                        rejected["width"] += 1
                    elif NOT_PANEL.search(page["title"]) or NOT_PANEL.search(desc):
                        rejected["not_panel"] += 1
                    else:
                        ext = ".png" if info["mime"] == "image/png" else ".jpg"
                        dest = raw / f"{info['sha1']}{ext}"
                        if not dest.exists():
                            req = urllib.request.Request(
                                info.get("thumburl") or info["url"], headers={"User-Agent": UA}
                            )
                            with urllib.request.urlopen(req, timeout=120) as r:
                                dest.write_bytes(r.read())
                            time.sleep(0.5)
                        rows.append(
                            {
                                "file": dest.name,
                                "title": page["title"],
                                "url": info["descriptionurl"],
                                "license": lic,
                                "author": strip_html(em.get("Artist")) or "",
                                "credit": strip_html(em.get("Credit")) or "",
                                "category": cat,
                                "width": info["width"],
                                "height": info["height"],
                            }
                        )
                        taken += 1
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PANEL_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} panels → {csv_path} · rejected {rejected}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panels", type=int, default=0, help="demo panel collection: number of panels (e.g. 150)")
    ap.add_argument("--targeted", action="store_true", help="per-category collection from TARGETED")
    ap.add_argument("--per-category", type=int, default=60, help="targeted mode: max new images per category")
    ap.add_argument("--max", type=int, default=600, help="broad mode: max candidates in total")
    ap.add_argument("--depth", type=int, default=None, help="subcategory depth (default: broad 2, targeted 1)")
    args = ap.parse_args()
    if args.panels:
        panels(args.panels, 2 if args.depth is None else args.depth)
        return
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    meta_path = OUT / "candidates.jsonl"
    done = {json.loads(line)["title"] for line in meta_path.open(encoding="utf-8")} if meta_path.exists() else set()
    rejected = {"license": 0, "mime": 0, "size": 0}
    with meta_path.open("a", encoding="utf-8") as meta:
        if args.targeted:
            depth = 1 if args.depth is None else args.depth
            for cat in TARGETED:
                files = walk([cat], depth)
                titles = [t for t in files if t not in done]
                n = download(titles, files, "targeted", args.per_category, meta, rejected)
                done |= set(titles)
                print(f"  {cat}: +{n}")
        else:
            files = walk(CATEGORIES, 2 if args.depth is None else args.depth)
            titles = [t for t in files if t not in done]
            download(titles, files, "broad", args.max - len(done), meta, rejected)
    total = sum(1 for _ in meta_path.open(encoding="utf-8"))
    print(f"{total} candidates in total · rejected {rejected} · metadata: {meta_path}")


if __name__ == "__main__":
    main()
