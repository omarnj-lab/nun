"""Synthetic calligraphy renderer (M4 smoke: one verse, one font). The full renderer is M7 (SPEC §6.2).

The rendered text is always taken word-for-word from the corpus (never typed), and the label records the exact
span. Arabic shaping requires Pillow's RAQM layout engine (libraqm); rendering refuses to run without it.

    python -m training.synth.render --smoke   → data/synth/smoke/{20-114.png, 20-114.basic.png, labels.jsonl}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, features

from nun.corpus.store import CorpusStore
from training.synth.fonts import ensure

OUT = Path("data/synth/smoke")


def require_raqm() -> None:
    if not features.check("raqm"):
        raise RuntimeError("Pillow has no RAQM support: Arabic would render unshaped (install libraqm)")


def render(text: str, font_path: Path, size: int = 96, engine=ImageFont.Layout.RAQM, pad: int = 48) -> Image.Image:
    font = ImageFont.truetype(str(font_path), size, layout_engine=engine)
    opts = {"direction": "rtl", "language": "ar"} if engine == ImageFont.Layout.RAQM else {}
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    x0, t, r, b = probe.textbbox((0, 0), text, font=font, **opts)
    img = Image.new("RGB", (r - x0 + 2 * pad, b - t + 2 * pad), (246, 240, 226))
    ImageDraw.Draw(img).text((pad - x0, pad - t), text, font=font, fill=(20, 32, 31), **opts)
    return img


def smoke() -> dict:
    require_raqm()
    store = CorpusStore()
    rec = store.get(20, 114)
    words = rec.text_simple.split()
    span = " ".join(words[-4:])  # the commonly inscribed ending of 20:114, cut from the corpus words
    font = ensure("amiri/Amiri-Regular.ttf")
    OUT.mkdir(parents=True, exist_ok=True)
    shaped = render(span, font)
    basic = render(span, font, engine=ImageFont.Layout.BASIC)
    shaped.save(OUT / "20-114.png")
    basic.save(OUT / "20-114.basic.png")  # unshaped control, for eyeballing the difference
    differs = shaped.size != basic.size or ImageChops.difference(shaped, basic).getbbox() is not None
    label = {
        "file": "20-114.png",
        "text": span,
        "refs": [{"sura": 20, "aya_from": 114, "aya_to": 114}],
        "font": font.name,
        "style": ["Naskh"],
        "theme": "quranic",
        "shaping": "raqm",
        "shaped_differs_from_unshaped": differs,
    }
    (OUT / "labels.jsonl").write_text(json.dumps(label, ensure_ascii=False) + "\n", encoding="utf-8")
    if not differs:
        raise RuntimeError("shaped and unshaped renders are identical: shaping is not active")
    return label


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", required=True)
    print(json.dumps(smoke(), ensure_ascii=False))
