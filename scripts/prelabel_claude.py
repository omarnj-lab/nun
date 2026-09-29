"""Test set B: pre-label Commons candidates with Claude vision, verified against the corpus; a human confirms.

For each candidate Claude returns a structured reading (transcription with [؟], content type, style, theme, flags).
The Quran reference is then taken from OUR corpus lookup of that transcription, never from the model alone: exact
match → all occurrences; else fuzzy ≥ 85; a model-only guess is kept but marked UNVERIFIED for the reviewer.
Each result is appended to the label log as labeller "claude-opus-5 (pre-label)", so it appears in the labelling
tool's Review mode, where a person confirms or rejects it. Unusable images (not calligraphy, unreadable, an
identifiable person) are logged as "skip" and never shown.

    python scripts/prelabel_claude.py --limit 5        # try a few, print the projected cost
    python scripts/prelabel_claude.py                  # all targeted + a 60-image sample of the broad pool

Raw model outputs + token usage: data/real/commons/prelabels.jsonl (gitignored).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from label_tool.app import STYLES, THEMES, append, candidates, image_id, image_path, state  # noqa: E402

from eval.sets import _index, _list  # noqa: E402
from nun.corpus.fragment import locate_fuzzy  # noqa: E402
from nun.normalize.arabic import normalize, normalize_ns, split_segments  # noqa: E402

MODEL = "claude-opus-5"
LABELLER = "claude-opus-5 (pre-label)"
RAW = Path("data/real/commons/prelabels.jsonl")
PRICE_IN, PRICE_OUT = 5.00 / 1e6, 25.00 / 1e6  # $/token, claude-opus-5 (claude-api skill, cached 2026-06-24)
BROAD_SAMPLE = 60

SYSTEM = """You help build an evaluation set for an app that identifies Arabic calligraphy in photos (mosques, \
museums, heritage sites). For each photo, report what is visibly written.

Rules:
- Transcribe only what you can actually see. Put [؟] for any part you cannot read with confidence. Never complete \
a verse, supplication or name from memory beyond the visible text; a partial reading is expected and useful.
- One line per separate text segment (e.g. a roundel, a band, a line).
- content_type: quran (Quranic text), name_of_allah (a Name of Allah or "الله" alone), dhikr_or_dua (a common \
invocation that is not Quranic, e.g. «سبحان الله وبحمده»), hadith, name_of_person (the Prophet, companions, \
people, places), poetry_or_other (poetry, dedications, dates, signatures, decoration), unreadable.
- quran_ref: your best guess at the verse only if content_type is quran, otherwise all zeros. It is checked \
against the Quran text afterwards, so give 0 rather than guess when unsure.
- styles: the calligraphic style(s) visible, from the fixed list. theme: exactly one value from the fixed list.
- identifiable_person: true if a real person's face is clearly recognisable in the photo.
- is_arabic_calligraphy: false for photos where Arabic script is absent or incidental (a street sign, a book cover \
with Latin text, a flag seen from afar)."""

SCHEMA = {
    "type": "object",
    "properties": {
        "is_arabic_calligraphy": {"type": "boolean"},
        "readable": {"type": "string", "enum": ["fully", "partly", "no"]},
        "transcription": {"type": "string"},
        "content_type": {
            "type": "string",
            "enum": [
                "quran",
                "name_of_allah",
                "dhikr_or_dua",
                "hadith",
                "name_of_person",
                "poetry_or_other",
                "unreadable",
            ],
        },
        "quran_ref": {
            "type": "object",
            "properties": {"sura": {"type": "integer"}, "aya_from": {"type": "integer"}, "aya_to": {"type": "integer"}},
            "required": ["sura", "aya_from", "aya_to"],
            "additionalProperties": False,
        },
        "styles": {"type": "array", "items": {"type": "string", "enum": STYLES}},
        "theme": {"type": "string", "enum": THEMES},
        "identifiable_person": {"type": "boolean"},
        "notes": {"type": "string"},
    },
    "required": [
        "is_arabic_calligraphy",
        "readable",
        "transcription",
        "content_type",
        "quran_ref",
        "styles",
        "theme",
        "identifiable_person",
        "notes",
    ],
    "additionalProperties": False,
}


def encode(path: Path) -> tuple[str, str]:
    img = Image.open(path).convert("RGB")
    img.thumbnail((1568, 1568))  # the API's own long-side limit; avoids paying for pixels it would drop
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return "image/jpeg", base64.standard_b64encode(buf.getvalue()).decode()


def ask(client: anthropic.Anthropic, path: Path) -> tuple[dict | None, dict]:
    media, data = encode(path)
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                    {"type": "text", "text": "Report what is written in this photo."},
                ],
            }
        ],
    )
    usage = {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens, "model": resp.model}
    if resp.stop_reason == "refusal":
        return None, usage | {"stop": "refusal"}
    if resp.stop_reason == "max_tokens":
        return None, usage | {"stop": "max_tokens"}
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text), usage | {"stop": resp.stop_reason}


MAX_OCCURRENCES = 12  # a line found in more places than this (e.g. «الله», «رسوله») cannot identify a verse


def clean_reading(transcription: str) -> str:
    """Drop the model's layout notes: «(…)» parentheticals and «label:» prefixes (inscriptions never contain ':')."""
    lines = []
    for line in transcription.splitlines():
        line = re.sub(r"\([^)]*\)", " ", line)
        lines.append(line.rsplit(":", 1)[-1])
    return "\n".join(lines)


def locate_lines(transcription: str) -> tuple[list[dict], str, str]:
    """Locate a multi-line reading line by line → (merged refs, corpus fragments, how).

    Each segment (split on newlines and [؟]) is located on its own. A Basmala is treated as a sura header when other
    lines are located. Segments found in several places keep only the occurrences inside a sura that another,
    unambiguous segment pins down. Located ayahs of one sura are merged into ranges (gaps ≤ 2 ayahs).
    """
    idx = _index()
    basmala_ns = "".join(w.ns for w in idx.words[:4])  # 1:1
    found: list[tuple[str, list[dict]]] = []
    fuzzy_scores = []
    for seg in split_segments(clean_reading(transcription)):
        q_ns = normalize_ns(seg)
        if len(q_ns) < 4:
            continue
        hits = idx.find_exact(q_ns) or (idx.find_exact(q_ns, whole_words=False) if len(q_ns) >= 8 else [])
        if len(hits) > MAX_OCCURRENCES:
            continue
        spans = [s for s in (idx.span(*h) for h in hits) if not s["cross_sura"]]
        if not spans and len(q_ns) >= 8 and (got := locate_fuzzy(idx, q_ns)) and got[1] >= 85:
            spans = [got[0]]  # spelling variants, e.g. رحمة read where the Quranic rasm has رحمت
            fuzzy_scores.append(round(got[1]))
        if spans:
            found.append((q_ns, spans))
    if len(found) > 1:
        found = [f for f in found if f[0] != basmala_ns] or found
    if not found:
        return [], "", "not found"
    how = "line by line: exact" + (f" + fuzzy {fuzzy_scores}" if fuzzy_scores else "")
    pinned = {f[1][0]["sura"] for f in found if len({s["sura"] for s in f[1]}) == 1}
    spans = []
    for _, sp in found:
        kept = [s for s in sp if s["sura"] in pinned] if pinned else sp
        spans += kept or sp
    by_sura: dict[int, list[dict]] = {}
    for s in sorted(spans, key=lambda s: (s["sura"], s["aya_from"])):
        rs = by_sura.setdefault(s["sura"], [])
        if rs and s["aya_from"] <= rs[-1]["aya_to"] + 2:
            rs[-1]["aya_to"] = max(rs[-1]["aya_to"], s["aya_to"])
        else:
            rs.append({"sura": s["sura"], "aya_from": s["aya_from"], "aya_to": s["aya_to"]})
    refs = [r for rs in by_sura.values() for r in rs]
    frags = " | ".join(dict.fromkeys(s["fragment"] for s in spans))
    return refs, frags, how


def to_label(cid: str, out: dict) -> dict:
    """Turn Claude's reading into a label event; the Quran reference comes from the corpus."""
    base = {"event": "label", "id": cid, "labeller": LABELLER, "refs": [], "list_ids": []}
    base |= {"style": out["styles"], "theme": out["theme"], "gt_text": out["transcription"].strip()}
    if not out["is_arabic_calligraphy"] or out["readable"] == "no" or out["identifiable_person"]:
        why = "identifiable person" if out["identifiable_person"] else "not calligraphy / unreadable"
        return base | {"gt_type": "skip", "notes": f"auto-skip: {why}"}
    notes = [f"model reading: {out['transcription']}", f"model type: {out['content_type']}"]
    if out["notes"]:
        notes.append(f"model notes: {out['notes']}")
    ctype = out["content_type"]
    if ctype == "quran":
        refs, frag, how = locate_lines(out["transcription"])
        guess = out["quran_ref"]
        if refs:
            agree = any(r["sura"] == guess["sura"] and r["aya_from"] <= guess["aya_from"] <= r["aya_to"] for r in refs)
            notes.append(
                f"corpus {how}; model guess {guess['sura']}:{guess['aya_from']} {'agrees' if agree else 'DISAGREES'}"
            )
            if len(refs) > 4:
                notes.append(f"WEAK: the readable fragment occurs in {len(refs)} places; confirm only if it is clear")
            return base | {"gt_type": "quran", "refs": refs, "gt_text": frag, "notes": " · ".join(notes)}
        if guess["sura"]:
            notes.append("UNVERIFIED: reading not found in corpus; reference is the model's guess only")
            return base | {"gt_type": "quran", "refs": [guess], "notes": " · ".join(notes)}
        ctype = "poetry_or_other"
        notes.append("model said quran but gave no reference and the reading is not in the corpus")
    if ctype in ("name_of_allah", "dhikr_or_dua"):
        kind = "names" if ctype == "name_of_allah" else "dhikr"
        lines = split_segments(out["transcription"])  # normalised, in reading order
        segs = set(lines) | {normalize(" ".join(lines))}
        ids = [e["id"] for e in _list(kind) if e["text_norm"] in segs]
        if ids:
            gt = "name" if kind == "names" else "dhikr"
            return base | {"gt_type": gt, "list_ids": ids, "notes": " · ".join(notes)}
        notes.append(f"no exact match in the {kind} list")
    return base | {"gt_type": "other", "notes": " · ".join(notes)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rederive", action="store_true", help="rebuild labels from saved outputs; no API calls")
    args = ap.parse_args()
    st = state()
    if args.rederive:
        changed = 0
        keys = ("gt_type", "refs", "list_ids", "gt_text", "notes")
        for line in RAW.open(encoding="utf-8"):
            row = json.loads(line)
            prev = st.get(row["id"], {})
            old = prev.get("label", {})
            # only unreviewed pre-labels are refreshed; human labels and reviewed items are never touched
            if row["output"] is None or old.get("labeller") != LABELLER or "review" in prev:
                continue
            new = to_label(row["id"], row["output"])
            if any(old.get(k) != new[k] for k in keys):
                append(new)
                changed += 1
        print(f"re-derived: {changed} labels changed")
        return
    todo = [c for c in candidates("commons") if image_id(c) not in st]
    targeted = [c for c in todo if c.get("pool") == "targeted"]
    broad = [c for c in todo if c.get("pool") != "targeted"]
    already_broad = sum(1 for c in candidates("commons") if c.get("pool") != "targeted" and image_id(c) in st)
    sample = random.Random(20261004).sample(broad, max(0, min(len(broad), BROAD_SAMPLE - already_broad)))
    queue = (targeted + sample)[: args.limit]
    print(f"pre-labelling {len(queue)} images ({len(targeted)} targeted, {len(sample)} broad-pool sample)")

    load_dotenv(override=True)  # the key in .env wins over any stale ANTHROPIC_API_KEY in the shell
    client = anthropic.Anthropic()
    lock = threading.Lock()
    totals = {"in": 0, "out": 0, "done": 0, "failed": 0}

    def work(c: dict) -> None:
        cid = image_id(c)
        try:
            out, usage = ask(client, image_path(c))
        except anthropic.APIStatusError as e:
            out, usage = None, {"stop": f"api_error {e.status_code}"}
        with lock:
            totals["in"] += usage.get("input", 0)
            totals["out"] += usage.get("output", 0)
            with RAW.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"id": cid, "usage": usage, "output": out}, ensure_ascii=False) + "\n")
            if out is None:
                totals["failed"] += 1
                print(f"  {cid}: no label ({usage.get('stop')})")
                return
            lab = to_label(cid, out)
            append(lab)
            totals["done"] += 1
            print(f"  {cid}: {lab['gt_type']:<6} {lab['refs'] or lab['list_ids'] or ''}")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, queue))
    cost = totals["in"] * PRICE_IN + totals["out"] * PRICE_OUT
    n = max(totals["done"] + totals["failed"], 1)
    print(f"done {totals['done']} · failed {totals['failed']} · tokens in {totals['in']:,} out {totals['out']:,}")
    print(f"cost ≈ ${cost:.2f} (≈ ${cost / n:.3f}/image)")


if __name__ == "__main__":
    main()
