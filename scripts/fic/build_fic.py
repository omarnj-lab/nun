"""INTERNAL test set from freeislamiccalligraphy.com (non-commercial internal testing only; never publish the images).

Steps 1–3 of the task: walk each style section's listing pages (?_page=N, 10 items each), keep Qur'an items whose
title looks like "Al-Anfal 8, 15" or "Al-Baqarah 2, 255-257" (≤ 60 per style), follow "Original Image"
(/view-image/?id=…) to the real file and download it, check every label against
analysis/v1_verse_id/quran_uthmani_quranenc.json, and write data/private/fic/labels.csv.
All requests go through scripts.fic.polite (robots.txt, 1 req/s, fixed User-Agent, cache).

    PYTHONPATH=. python -m scripts.fic.build_fic
"""

from __future__ import annotations

import csv
import html as H
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from scripts.fic.polite import BASE, get

STYLES = [
    "thuluth",
    "naskh",
    "diwani",
    "diwani-jelli",
    "eastern-kufic",
    "square-kufic",
    "fatimi-kufic-script",
    "muhaqaq",
    "moroccan",
]
PER_STYLE = 60
MAX_PAGES = 60  # bound the crawl per style even if Qur'an items are rare in a section
OUT = Path("data/private/fic")
QURAN = json.load(open("analysis/v1_verse_id/quran_uthmani_quranenc.json", encoding="utf-8"))
AYAHS = {(s, a): t for s, a, t in QURAN}
COUNTS = Counter(s for s, _, _ in QURAN)
TITLE = re.compile(r"^(?P<name>[^\d,]+?)\s+(?P<sura>\d{1,3})\s*,\s*(?P<a0>\d{1,3})(?:\s*[-–]\s*(?P<a1>\d{1,3}))?$")
ITEM = re.compile(r"<a[^>]+href=[\"']([^\"']*\?portfolio=[^\"'#]+)[\"'][^>]*>\s*([^<]{2,120}?)\s*</a>")


def sura_names() -> dict[int, str]:
    root = ET.parse("data/raw/tanzil/quran-data.xml").getroot()
    return {int(e.get("index")): e.get("tname") for e in root.iter("sura")}


def name_key(name: str) -> str:
    """Loose transliteration key: 'Al-A‘raf' / 'Al-Araaf' / 'al-a'raf' → 'araf'."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^(al|an|ar|as|ash|at|az|ad|adh)[-\s]", "", s)
    s = re.sub(r"[^a-z]", "", s)
    return re.sub(r"(.)\1+", r"\1", s).replace("aa", "a")


def skeleton(name: str) -> str:
    """Consonant skeleton without the article: 'Al-‘Imran' → 'mrn', 'Aal-i-Imraan' → 'lmrn', 'An-Noor' → 'nr'."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^(al|an|ar|as|ash|at|az|ad|adh)[-\s]", "", s)
    s = re.sub(r"[^a-z]|[aeiou]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def same_sura_name(a: str, b: str) -> bool:
    """Transliterations of one sura name differ widely (Al-‘Imran / Aal-i-Imraan, Al-Nur / An-Noor)."""
    ka, kb, sa, sb = name_key(a), name_key(b), skeleton(a), skeleton(b)
    return ka == kb or ka[:4] == kb[:4] or (min(len(sa), len(sb)) >= 2 and (sa.endswith(sb) or sb.endswith(sa)))


def parse_title(title: str) -> dict | None:
    m = TITLE.match(title.strip())
    if not m:
        return None
    a0 = int(m["a0"])
    return {"name": m["name"].strip(), "sura": int(m["sura"]), "aya_from": a0, "aya_to": int(m["a1"] or a0)}


def listing(style: str) -> list[tuple[str, str]]:
    """(item_url, title) for Qur'an items of one section, in listing order, ≤ PER_STYLE."""
    out, seen = [], set()
    url0 = f"{BASE}/homepage/all-calligraphy-items/{style}/"
    for page in range(1, MAX_PAGES + 1):
        page_html, _ = get(url0 if page == 1 else f"{url0}?_page={page}")
        items = [(u, H.unescape(t).strip()) for u, t in ITEM.findall(page_html)]
        items = [(u if u.startswith("http") else BASE + u, t) for u, t in items]
        new = [(u, t) for u, t in items if u not in seen]
        if not new:
            break  # past the last page
        for u, t in new:
            seen.add(u)
            if parse_title(t) and len(out) < PER_STYLE:
                out.append((u, t))
        if len(out) >= PER_STYLE:
            break
        total = re.search(r'data-totalpages="(\d+)"', page_html)
        if total and page >= int(total.group(1)):
            break
    return out


def original_image(item_url: str) -> tuple[str, str]:
    """→ (title from the item page, URL of the original image file)."""
    page, _ = get(item_url)
    title = H.unescape(re.findall(r"<h1[^>]*>(.*?)</h1>", page, re.S)[-1]).strip()
    view = re.search(r"href=[\"']([^\"']*/view-image/\?id=\d+)[\"'][^>]*>\s*Original Image", page)
    if not view:
        raise ValueError("no 'Original Image' link")
    vurl = view.group(1) if view.group(1).startswith("http") else BASE + view.group(1)
    vpage, _ = get(vurl)
    img = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", vpage)
    if not img:
        raise ValueError(f"no image on {vurl}")
    return title, img.group(1)


def main() -> None:
    names = sura_names()
    rows, failures, per_style = [], [], Counter()
    seen_items: dict[str, str] = {}
    for style in STYLES:
        for item_url, list_title in listing(style):
            if item_url in seen_items:
                failures.append(
                    {"item_url": item_url, "style": style, "problem": f"also listed under {seen_items[item_url]}"}
                )
                continue
            seen_items[item_url] = style
            try:
                title, img_url = original_image(item_url)
            except Exception as e:  # noqa: BLE001 — record and continue
                failures.append({"item_url": item_url, "style": style, "problem": f"download: {e}"})
                continue
            lab = parse_title(title) or parse_title(list_title)
            problems = []
            if not lab:
                problems.append(f"title not a Qur'an reference: {title!r}")
            else:
                s, a0, a1 = lab["sura"], lab["aya_from"], lab["aya_to"]
                if s not in COUNTS:
                    problems.append(f"sura {s} does not exist")
                elif not (1 <= a0 <= a1 <= COUNTS[s]):
                    problems.append(f"ayah {a0}-{a1} outside sura {s} (1-{COUNTS[s]})")
                elif not same_sura_name(lab["name"], names[s]):
                    problems.append(f"name {lab['name']!r} does not match sura {s} ({names[s]})")
            if problems:
                failures.append({"item_url": item_url, "style": style, "problem": "; ".join(problems)})
                continue
            body, _ = get(img_url, binary=True)
            ext = Path(img_url.split("?")[0]).suffix.lower() or ".jpg"
            slug = re.sub(r"[^a-z0-9-]+", "-", item_url.split("portfolio=")[-1].lower()).strip("-")
            dest = OUT / "images" / style / f"{slug}{ext}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
            text = " ".join(AYAHS[(s, a)] for a in range(a0, a1 + 1))
            rows.append(
                {
                    "file": str(dest.relative_to(OUT)),
                    "item_url": item_url,
                    "title": title,
                    "sura": s,
                    "aya_from": a0,
                    "aya_to": a1,
                    "style": style,
                    "uthmani_text": text,
                }
            )
            per_style[style] += 1
        print(f"{style}: {per_style[style]} items", flush=True)
    fields = ["file", "item_url", "title", "sura", "aya_from", "aya_to", "style", "uthmani_text"]
    with (OUT / "labels.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with (OUT / "label_failures.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item_url", "style", "problem"])
        w.writeheader()
        w.writerows(failures)
    print(json.dumps({"items": len(rows), "per_style": per_style, "failures": len(failures)}))


if __name__ == "__main__":
    main()
