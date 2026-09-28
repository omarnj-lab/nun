"""Systems under evaluation. Each maps (ground truth, image) → a prediction row (eval.metrics format).

The status rule here is the TEMPORARY gate (reading + exact/fuzzy location only). The calibrated gate with VLM
verification replaces it in M9 (SPEC §4.7).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PIL import Image

from eval.sets import _index, _list
from nun.corpus.fragment import locate_fuzzy
from nun.normalize.arabic import normalize, normalize_ns, split_segments


def decide(reading: str) -> dict:
    """Temporary gate: unique exact → verified · several exact / fuzzy ≥ 90 / list match → partial · else uncertain."""
    idx = _index()
    segments = split_segments(reading)
    q_ns = "".join(normalize_ns(s) for s in segments)
    if len(q_ns) < 2:
        return {"status": "uncertain", "refs": [], "candidates": [], "confidence": 0.0}
    hits = idx.find_exact(q_ns) or (idx.find_exact(q_ns, whole_words=False) if len(q_ns) >= 8 else [])
    spans = [s for s in (idx.span(*h) for h in hits) if not s["cross_sura"]]
    refs = [{k: s[k] for k in ("sura", "aya_from", "aya_to")} for s in spans]
    if len(refs) == 1:
        return {"status": "verified", "refs": refs, "candidates": [refs], "confidence": 0.95}
    if refs:
        return {"status": "partial", "refs": refs, "candidates": [[r] for r in refs[:5]], "confidence": 0.7}
    q_norm = normalize(" ".join(segments))
    for kind in ("names", "dhikr"):
        ids = [e["id"] for e in _list(kind) if e["text_norm"] == q_norm]
        if ids:
            return {"status": "partial", "refs": [], "list_ids": ids, "candidates": [], "confidence": 0.7}
    if len(q_ns) >= 8 and (got := locate_fuzzy(idx, q_ns)):
        sp, score = got
        ref = {k: sp[k] for k in ("sura", "aya_from", "aya_to")}
        status = "partial" if score >= 90 else "uncertain"
        return {
            "status": status,
            "refs": [ref] if status == "partial" else [],
            "candidates": [[ref]],
            "confidence": score / 100 * 0.8,
        }
    return {"status": "uncertain", "refs": [], "candidates": [], "confidence": 0.0}


def gold_reading() -> Callable[[dict, Callable[[], Image.Image]], dict]:
    """Upper bound for the search: the true text as the 'reading' (no GPU)."""

    def run(gt: dict, _image: Callable[[], Image.Image]) -> dict:
        t = time.perf_counter()
        pred = decide(gt["gt_text"])
        return {
            "id": gt["id"],
            "reading": gt["gt_text"],
            **pred,
            "timings_ms": {"total": round(1000 * (time.perf_counter() - t))},
        }

    return run


def v1_locate() -> Callable[[dict, Callable[[], Image.Image]], dict]:
    """SPEC §10 baseline (4): KhaṭṭVision v1 full-image reading + corpus location."""
    from nun.vlm.khatt_v1 import KhattV1

    v1 = KhattV1()

    def run(gt: dict, image: Callable[[], Image.Image]) -> dict:
        t = time.perf_counter()
        reading, vlm_s = v1.read(image())
        t_search = time.perf_counter()
        pred = decide(reading)
        done = time.perf_counter()
        timings = {
            "vlm": round(1000 * vlm_s),
            "search": round(1000 * (done - t_search)),
            "total": round(1000 * (done - t)),
        }
        return {"id": gt["id"], "reading": reading, **pred, "timings_ms": timings}

    return run


SYSTEMS = {"gold-reading": gold_reading, "v1-locate": v1_locate}
