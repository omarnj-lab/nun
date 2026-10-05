"""The reading path (PLAN_NOW step 2): a panel not in the collection is READ BY KhaṭṭVision first; its reading is
snapped to the nearest passage of the Quran (the visitor sees the Mushaf text, never the model's reading); an
independent check confirms the passage before it is shown. Otherwise the visitor still gets what the model saw
(script style, where the text is, whether it looks Quranic), never a guessed verse.

Measured on the team's 195-panel internal set (eval/results/2026-10-05/reading_gate.md), wrong verses shown:
  KhaṭṭVision + nearest passage, no check ............ 29.7% of panels (the model can recall a fluent wrong verse)
  + independent check (nun.vision_check) agrees ...... 1.0%  (25% of panels identified, every script)
  no check available → strict gate (Naskh, ≥ 30 letters) 0.5% (16% identified)
"""

from __future__ import annotations

from nun.retrieval.verse_search import Hit, searcher

MIN_SCORE = 90  # reading vs Quran passage (rapidfuzz, 0-100)
MIN_LETTERS = 15  # with the independent check
STRICT_MIN_LETTERS = (
    30  # without it: short famous phrases (55:13, 2:156) are where the model recalls instead of reading
)
RELIABLE_STYLES = {"Naskh"}


def candidate(analysis: dict) -> tuple[Hit | None, str]:
    """KhaṭṭVision's reading → the nearest Quran passage, or the reason there is none."""
    theme = analysis.get("theme")
    if theme and theme != "quranic":
        return None, "theme"
    lines = [r["text"] for r in analysis.get("regions", []) if r.get("text")]
    if not lines:
        return None, "no_text"
    best, hits = searcher().read(lines)
    if best is None or best.basmala or best.score < MIN_SCORE or best.qlen < MIN_LETTERS:
        return None, "weak_match"
    for h in hits:
        if h is not best and not h.basmala and h.qlen >= 8 and h.score >= 80 and not best.overlaps(h):
            return None, "lines_disagree"
    return best, "ok"


def decide(analysis: dict, check: dict | None = None) -> dict:
    """analysis: KhaṭṭVision structured output {styles, theme, regions[{box, text}]}; check: the independent
    identification ({sura, aya_from, aya_to} | {"unknown": True}) or None if unavailable →
    {status: read | not_quranic | unsure, reason, sura?, aya_from?, aya_to?, score?, letters?, checked}."""
    styles = analysis.get("styles") or []
    base = {"styles": styles, "theme": analysis.get("theme"), "checked": False}
    best, why = candidate(analysis)
    if best is None:
        return base | {"status": "not_quranic" if why == "theme" else "unsure", "reason": why}
    found = {
        "sura": best.sura,
        "aya_from": best.aya_from,
        "aya_to": best.aya_to,
        "score": round(best.score, 1),
        "letters": best.qlen,
    }
    if check is not None:
        if check.get("unknown"):
            return base | {"status": "unsure", "reason": "check_unknown"}
        agree = check["sura"] == best.sura and best.aya_from <= check["aya_to"] and check["aya_from"] <= best.aya_to
        if not agree:
            return base | {"status": "unsure", "reason": "check_disagrees"}
        return base | found | {"status": "read", "reason": "ok", "checked": True}
    # no independent check: only what the model reads reliably on its own
    if not set(styles) & RELIABLE_STYLES:
        return base | {"status": "unsure", "reason": "ornate_style"}
    if best.qlen < STRICT_MIN_LETTERS:
        return base | {"status": "unsure", "reason": "weak_match"}
    return base | found | {"status": "read", "reason": "ok"}
