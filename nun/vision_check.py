"""Independent check for the reading path: a second vision model (Claude) is asked, without seeing KhaṭṭVision's
answer, which Quran verse the photo shows. Nūn shows a verse read by KhaṭṭVision only when the two agree.

Measured on the 195-panel internal set (eval/results/2026-10-05/reading_gate.md): KhaṭṭVision alone would show a wrong
verse on 29.7% of panels; with this check 1.0%, while keeping KhaṭṭVision's 25% correct identifications.
The photo is sent to the Anthropic API for this check only (in memory, not stored by Nūn).
"""

from __future__ import annotations

import base64
import io
import json
import re

from PIL import Image

MODEL = "claude-opus-5"
PROMPT = (
    "This image shows Arabic calligraphy. If it is a verse of the Quran, identify it. "
    'Reply with JSON only: {"sura": <number>, "aya_from": <number>, "aya_to": <number>} for the verse(s) shown, '
    'or {"unknown": true} if you cannot identify a Quran verse with confidence. Do not guess.'
)
_client = None


def _jpeg_b64(im: Image.Image, max_side: int = 1568) -> str:
    im = im.convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def identify(im: Image.Image) -> dict | None:
    """→ {sura, aya_from, aya_to}, {"unknown": True}, or None when the check is unavailable."""
    global _client
    try:
        import anthropic
        from dotenv import load_dotenv

        if _client is None:
            load_dotenv(override=True)
            _client = anthropic.Anthropic()
        r = _client.messages.create(
            model=MODEL,
            max_tokens=16000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": _jpeg_b64(im)},
                        },
                        {"type": "text", "text": PROMPT},
                    ],
                }
            ],
        )
        text = "".join(b.text for b in r.content if b.type == "text")
    except Exception:  # noqa: BLE001 — no check available: the caller falls back to the strict gate
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"unknown": True}
    try:
        d = json.loads(m.group(0))
        if d.get("unknown"):
            return {"unknown": True}
        a = int(d["aya_from"])
        return {"sura": int(d["sura"]), "aya_from": a, "aya_to": int(d.get("aya_to") or a)}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {"unknown": True}
