"""Text regions from KhaṭṭVision's structured output, aligned to the words of the verified verse.

The model's reading is used ONLY to find which verse words each region holds; the UI never shows the reading.
The words themselves always come from the corpus (`text_display`), indexed as (aya, token index) where tokens are
`text_display.split(" ")`.
"""

from __future__ import annotations

import json
import re

from rapidfuzz import fuzz

from nun.normalize.arabic import normalize_ns

STYLES = ["Thuluth", "Diwani", "Naskh", "Kufic", "Ruq'ah", "Nasta'liq"]
MIN_ALIGN = 70  # rapidfuzz ratio (0-100) between a region's reading and its best verse span

_REGION = re.compile(
    r'"bbox_1000_xywh"\s*:\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,'
    r'\s*(-?\d+(?:\.\d+)?)\s*\]\s*,\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"'
)
_STYLES = re.compile(r'"styles"\s*:\s*\[([^\]]*)\]')


def parse(raw: str) -> dict:
    """→ {styles, regions[{box: [x0, y0, x1, y1] fractions, text}]}. Tolerates output cut off by the token cap."""
    regions = []
    for x, y, w, h, text in _REGION.findall(raw):
        x0, y0 = float(x) / 1000, float(y) / 1000
        x1, y1 = x0 + float(w) / 1000, y0 + float(h) / 1000
        box = [round(min(max(v, 0.0), 1.0), 4) for v in (x0, y0, x1, y1)]
        if box[2] - box[0] < 0.01 or box[3] - box[1] < 0.01:
            continue
        try:
            text = json.loads(f'"{text}"')
        except json.JSONDecodeError:
            pass
        if any(r["box"] == box for r in regions):
            continue
        regions.append({"box": box, "text": text})
    styles: list[str] = []
    m = _STYLES.search(raw)
    if m:
        styles = [s for s in STYLES if f'"{s}"' in m.group(1)]
    return {"styles": styles, "regions": regions}


def verse_words(ayahs: list[dict]) -> list[tuple[int, int, str]]:
    """(aya, token index, normalised word) for each display-text token with letters (pause marks skipped)."""
    out = []
    for a in ayahs:
        for i, tok in enumerate(a["text_display"].split(" ")):
            n = normalize_ns(tok)
            if n:
                out.append((a["aya"], i, n))
    return out


def align(text: str, words: list[tuple[int, int, str]]) -> list[list[int]]:
    """The contiguous verse span that best matches a region's reading → [[aya, token index], ...] ([] if none fits)."""
    reading = normalize_ns(text)
    if not reading or not words:
        return []
    k = max(1, len(text.split()))
    best, best_span = 0.0, None
    for length in range(max(1, k - 2), min(len(words), k + 2) + 1):
        for s in range(len(words) - length + 1):
            score = fuzz.ratio(reading, "".join(w[2] for w in words[s : s + length]))
            if score > best:
                best, best_span = score, (s, s + length)
    if best < MIN_ALIGN or best_span is None:
        return []
    return [[w[0], w[1]] for w in words[best_span[0] : best_span[1]]]


def regions_for_card(parsed: dict, ayahs: list[dict]) -> list[dict]:
    """Regions with their verse words; the reading itself is dropped here so it can never reach the UI."""
    words = verse_words(ayahs)
    return [{"box": r["box"], "words": align(r["text"], words)} for r in parsed["regions"]]
