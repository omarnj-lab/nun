"""Verse recognition from a calligraphy photo: general-purpose vision LLMs vs the team's KhaṭṭVision.

Task: given the image, name the Quran verse (surah:ayah) or say it cannot. Scored per image:
  correct            the predicted ayah(s) share text with a labelled ayah (repeated verses count, as in v1 scoring)
  wrong              a verse was named and it is not the labelled one ("confidently wrong")
  abstained          the system said it could not identify it
Reported per style: accuracy (correct / all), answered %, precision (correct / answered), wrong %.

KhaṭṭVision rows come from the cached v1 run (data/private/fic/v1_scores.csv: reading → corpus search; answered =
match score ≥ 90). External models are called only with --allow-external, because the internal test images must not
leave the machine without the team's approval.

    PYTHONPATH=. python eval/recognition_compare.py --systems khattvision claude-opus-5 gpt-5 --allow-external
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import io
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image

from nun.corpus.store import CorpusStore
from nun.normalize.arabic import normalize_ns

FIC = Path("data/private/fic")
PROMPT = (
    "This image shows Arabic calligraphy. If it is a verse of the Quran, identify it. "
    'Reply with JSON only: {"sura": <number>, "aya_from": <number>, "aya_to": <number>} for the verse(s) shown, '
    'or {"unknown": true} if you cannot identify a Quran verse with confidence. Do not guess.'
)
STYLE_ORDER = ["naskh", "thuluth", "diwani", "diwani-jelli", "fatimi-kufic-script", "square-kufic", "muhaqaq"]


def load_labels() -> list[dict]:
    with (FIC / "labels.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ayah_texts(store: CorpusStore, sura: int, a: int, b: int) -> set[str]:
    out = set()
    for aya in range(a, b + 1):
        try:
            out.add(normalize_ns(store.get(sura, aya).text_simple))
        except KeyError:
            pass
    return out


def is_correct(store: CorpusStore, label: dict, pred: dict) -> bool:
    want = ayah_texts(store, int(label["sura"]), int(label["aya_from"]), int(label["aya_to"]))
    got = ayah_texts(store, pred["sura"], pred["aya_from"], pred["aya_to"])
    return bool(want & got)


def image_b64(path: Path, max_side: int = 1568) -> str:
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im = im.convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()


def parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if d.get("unknown"):
        return None
    try:
        s, a = int(d["sura"]), int(d["aya_from"])
        return {"sura": s, "aya_from": a, "aya_to": int(d.get("aya_to") or a)}
    except (KeyError, TypeError, ValueError):
        return None


def ask_claude(model: str, b64: str) -> str:
    import anthropic
    from dotenv import load_dotenv

    load_dotenv(override=True)
    client = anthropic.Anthropic()
    r = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    )
    return "".join(b.text for b in r.content if b.type == "text")


def ask_openai(model: str, b64: str) -> str:
    import httpx
    from dotenv import load_dotenv

    load_dotenv(override=True)
    key = os.environ["OPENAI_API_KEY"]
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"},
                    {"type": "input_text", "text": PROMPT},
                ],
            }
        ],
    }
    r = httpx.post(
        "https://api.openai.com/v1/responses", json=body, headers={"Authorization": f"Bearer {key}"}, timeout=120
    )
    r.raise_for_status()
    out = r.json()
    return out.get("output_text") or "".join(
        c.get("text", "") for o in out.get("output", []) for c in o.get("content", []) if isinstance(c, dict)
    )


def run_external(system: str, labels: list[dict], store: CorpusStore, cache: Path) -> list[dict]:
    cache.mkdir(parents=True, exist_ok=True)
    out_file = cache / f"{system}.jsonl"
    done = {}
    if out_file.exists():
        done = {json.loads(x)["file"]: json.loads(x) for x in out_file.read_text(encoding="utf-8").splitlines() if x}
    rows = []
    with out_file.open("a", encoding="utf-8") as f:
        for lab in labels:
            if lab["file"] in done:
                rows.append(done[lab["file"]])
                continue
            t = time.perf_counter()
            try:
                b64 = image_b64(FIC / lab["file"])
                text = ask_claude(system, b64) if system.startswith("claude") else ask_openai(system, b64)
                err = None
            except Exception as e:  # noqa: BLE001
                text, err = "", str(e)[:200]
            row = {"file": lab["file"], "raw": text[:300], "error": err, "seconds": round(time.perf_counter() - t, 1)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            print(f"[{system}] {lab['file']} → {text[:60]!r}", flush=True)
    return rows


def score(system: str, labels: list[dict], store: CorpusStore, cache: Path) -> list[dict]:
    if system == "khattvision":
        with (FIC / "v1_scores.csv").open(encoding="utf-8") as f:
            v1 = {r["file"]: r for r in csv.DictReader(f)}
        out = []
        for lab in labels:
            r = v1[lab["file"]]
            answered = r["answered90"] == "True"
            out.append(
                {
                    "file": lab["file"],
                    "style": lab["style"],
                    "answered": answered,
                    "correct": answered and r["top1"] == "True",
                }
            )
        return out
    rows = {r["file"]: r for r in run_external(system, labels, store, cache)}
    out = []
    for lab in labels:
        pred = parse(rows[lab["file"]]["raw"])
        out.append(
            {
                "file": lab["file"],
                "style": lab["style"],
                "answered": pred is not None,
                "correct": pred is not None and is_correct(store, lab, pred),
            }
        )
    return out


def table(results: dict[str, list[dict]]) -> str:
    lines = [
        "| system | style | n | accuracy | answered | precision | confidently wrong |",
        "|---|---|---|---|---|---|---|",
    ]
    for system, rows in results.items():
        groups = defaultdict(list)
        for r in rows:
            groups[r["style"]].append(r)
        order = [s for s in STYLE_ORDER if s in groups] + sorted(set(groups) - set(STYLE_ORDER)) + ["**all**"]
        groups["**all**"] = rows
        for st in order:
            g = groups[st]
            n, c, a = len(g), sum(r["correct"] for r in g), sum(r["answered"] for r in g)
            prec = f"{100 * c / a:.0f}%" if a else "–"
            lines.append(
                f"| {system} | {st} | {n} | {100 * c / n:.1f}% | {100 * a / n:.0f}% | {prec} | {100 * (a - c) / n:.1f}% |"
            )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="+", default=["khattvision"])
    ap.add_argument("--allow-external", action="store_true", help="send the internal test images to external APIs")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    external = [s for s in args.systems if s != "khattvision"]
    if external and not args.allow_external:
        raise SystemExit(f"refusing to send internal images to {external}: add --allow-external once the team approves")
    store = CorpusStore()
    labels = load_labels()[: args.limit or None]
    cache = FIC / "compare_cache"
    results = {s: score(s, labels, store, cache) for s in args.systems}
    md = table(results)
    out = FIC / f"recognition_compare_{dt.date.today().isoformat()}.md"  # stays in data/private (git-ignored)
    out.write_text(
        f"# Verse recognition: {', '.join(args.systems)}\n\n{len(labels)} internal images.\n\n{md}\n", encoding="utf-8"
    )
    print(md)


if __name__ == "__main__":
    main()
