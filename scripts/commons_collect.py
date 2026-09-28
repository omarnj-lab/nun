"""M3: collect candidate real-world calligraphy photos from Wikimedia Commons for the `real-test` set.

Walks the categories in SOURCES.md §5 (+ subcategories to --depth), keeps only files whose license is
CC0 / Public domain / CC BY / CC BY-SA (no NC/ND/GFDL-only/fair use), and saves a ≤1600 px rendition plus
metadata (license, author, credit, source URL, sha1) to data/real/commons/. Candidates are then labelled
with the labelling tool; unlabelled or "other/unreadable" images are simply not used.

Usage: python scripts/commons_collect.py [--max 600] [--depth 2]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = "NunTestSetCollector/0.1 (research test set for an Islamic-content AI challenge; https://huggingface.co/NAMAA-Space)"
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=600, help="max candidates to download")
    ap.add_argument("--depth", type=int, default=2)
    args = ap.parse_args()
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    meta_path = OUT / "candidates.jsonl"
    done = {json.loads(line)["title"] for line in meta_path.open(encoding="utf-8")} if meta_path.exists() else set()

    files = walk(CATEGORIES, args.depth)
    titles = [t for t in files if t not in done]
    kept, rejected = len(done), {"license": 0, "mime": 0, "size": 0}
    with meta_path.open("a", encoding="utf-8") as meta:
        for i in range(0, len(titles), 50):
            if kept >= args.max:
                break
            d = api(
                action="query",
                titles="|".join(titles[i : i + 50]),
                prop="imageinfo",
                iiprop="url|extmetadata|sha1|size|mime",
                iiurlwidth="1600",
            )
            for page in d.get("query", {}).get("pages", []):
                if kept >= args.max:
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
                    url = info.get("thumburl") or info["url"]
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
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
                    "category": files[page["title"]],
                    "width": info["width"],
                    "height": info["height"],
                }
                meta.write(json.dumps(row, ensure_ascii=False) + "\n")
                meta.flush()
                kept += 1
    print(f"kept {kept} candidates · rejected {rejected} · metadata: {meta_path}")


if __name__ == "__main__":
    main()
