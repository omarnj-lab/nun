"""Evaluation metrics (SPEC §10). Pure functions over ground-truth and prediction rows.

Ground truth row: {id, gt_type: quran|name|dhikr|other, refs: [{sura, aya_from, aya_to}], list_ids, gt_text}
Prediction row:   {id, status: verified|partial|uncertain|out_of_scope, refs: [...], candidates: [[refs], ...],
                   confidence: float|None, reading: str|None, timings_ms: {...}}
"""

from __future__ import annotations

from statistics import median

from jiwer import cer as _cer
from jiwer import wer as _wer

from nun.normalize.arabic import normalize

ANSWERED = {"verified", "partial"}
ABSTAINED = {"uncertain", "out_of_scope"}


def overlaps(a: dict, b: dict) -> bool:
    return a["sura"] == b["sura"] and a["aya_from"] <= b["aya_to"] and b["aya_from"] <= a["aya_to"]


def refs_hit(pred: list[dict], gold: list[dict]) -> bool:
    return any(overlaps(p, g) for p in pred for g in gold)


def is_correct(gt: dict, pr: dict) -> bool:
    """Is the answer the system SHOWS (status verified/partial) right?"""
    if gt["gt_type"] == "quran":
        return refs_hit(pr.get("refs") or [], gt["refs"])
    if gt["gt_type"] in ("name", "dhikr"):
        return bool(set(pr.get("list_ids") or []) & set(gt.get("list_ids") or []))
    return False  # answering anything on an "other" image is wrong


def _safe(t: str | None) -> str:
    n = normalize(t or "")
    return n if n else "∅"


def reading_errors(gts: list[dict], prs: dict[str, dict]) -> dict:
    pairs = [(_safe(g["gt_text"]), _safe(prs[g["id"]].get("reading"))) for g in gts if g.get("gt_text")]
    if not pairs:
        return {"cer": None, "wer": None, "n": 0}
    refs, hyps = zip(*pairs, strict=True)
    return {
        "cer": round(_cer(list(refs), list(hyps)), 4),
        "wer": round(_wer(list(refs), list(hyps)), 4),
        "n": len(pairs),
    }


def compute(gts: list[dict], preds: list[dict]) -> dict:
    prs = {p["id"]: p for p in preds}
    missing = [g["id"] for g in gts if g["id"] not in prs]
    if missing:
        raise ValueError(f"{len(missing)} ground-truth items have no prediction, e.g. {missing[:3]}")
    n = len(gts)
    quran = [g for g in gts if g["gt_type"] == "quran"]
    in_scope = [g for g in gts if g["gt_type"] != "other"]
    other = [g for g in gts if g["gt_type"] == "other"]

    top1 = [refs_hit(prs[g["id"]].get("refs") or [], g["refs"]) for g in quran]
    top5 = [
        any(refs_hit(c, g["refs"]) for c in (prs[g["id"]].get("candidates") or [])[:5])
        or refs_hit(prs[g["id"]].get("refs") or [], g["refs"])
        for g in quran
    ]
    answered = [g for g in in_scope if prs[g["id"]]["status"] in ANSWERED]
    confident_errors = [g for g in gts if prs[g["id"]]["status"] == "verified" and not is_correct(g, prs[g["id"]])]
    abstain_ok = [prs[g["id"]]["status"] in ABSTAINED for g in other]

    def rate(xs: list) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    lat = [p["timings_ms"].get("total") for p in preds if (p.get("timings_ms") or {}).get("total") is not None]
    lat_sorted = sorted(lat)
    return {
        "n": n,
        "mix": {t: sum(g["gt_type"] == t for g in gts) for t in ("quran", "name", "dhikr", "other")},
        "verse_id_top1": rate(top1),
        "verse_id_top5": rate(top5),
        "coverage": rate([g in answered for g in in_scope]),
        "selective_accuracy": rate([is_correct(g, prs[g["id"]]) for g in answered]),
        "confident_error_rate": round(len(confident_errors) / n, 4) if n else None,
        "confident_errors": [g["id"] for g in confident_errors],
        "abstention_correctness": rate(abstain_ok),
        "reading": reading_errors(gts, prs),
        "status_counts": {s: sum(p["status"] == s for p in preds) for s in (*ANSWERED, *ABSTAINED)},
        "latency_ms": {
            "p50": round(median(lat)) if lat else None,
            "p95": lat_sorted[min(len(lat_sorted) - 1, int(0.95 * len(lat_sorted)))] if lat else None,
        },
    }


def coverage_curve(gts: list[dict], preds: list[dict]) -> list[dict]:
    """Selective accuracy vs coverage as the confidence threshold sweeps over the observed scores."""
    prs = {p["id"]: p for p in preds}
    in_scope = [g for g in gts if g["gt_type"] != "other"]
    scored = sorted(
        ((prs[g["id"]].get("confidence") or 0.0, is_correct(g, prs[g["id"]])) for g in in_scope), reverse=True
    )
    out, ok = [], 0
    for k, (conf, correct) in enumerate(scored, 1):
        ok += correct
        out.append({"threshold": round(conf, 4), "coverage": round(k / len(in_scope), 4), "accuracy": round(ok / k, 4)})
    return out
