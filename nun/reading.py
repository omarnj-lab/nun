"""The reading path (PLAN_NOW step 2): a panel that is not in the collection is read by KhaṭṭVision, and the
nearest place in the Quran is shown ONLY when the reading is safe to trust. Otherwise the visitor still gets what the
model saw (script style, where the text is, whether it looks Quranic), never a guessed verse.

Gate (calibrated on the team's 195-panel internal set with KhaṭṭVision's own style/theme labels,
eval/results/2026-10-05/reading_gate.md: 26 verses shown, 25 right, 1 wrong = 0.5% of panels):
  1. KhaṭṭVision's theme is "quranic" (otherwise: not a Quran verse → no verse shown);
  2. the script is one the model reads reliably (Naskh): on ornate scripts the model can write a fluent but wrong
     verse from memory, which no score threshold catches;
  3. the strongest line matches a Quran passage with score ≥ 90 over ≥ 30 letters, is not just the Basmala, and no
     other strong line points elsewhere.
"""

from __future__ import annotations

from nun.retrieval.verse_search import searcher

MIN_SCORE = 90
MIN_LETTERS = 30  # short famous phrases (e.g. 55:13, 2:156) are where the model recalls instead of reading
RELIABLE_STYLES = {"Naskh"}


def decide(analysis: dict) -> dict:
    """analysis: KhaṭṭVision structured output {styles, theme, regions[{box, text}]} →
    {status: read | not_quranic | unsure, reason, ref?, score?}. The model's reading never goes to the visitor."""
    styles = analysis.get("styles") or []
    theme = analysis.get("theme")
    lines = [r["text"] for r in analysis.get("regions", []) if r.get("text")]
    base = {"styles": styles, "theme": theme}
    if theme and theme != "quranic":
        return base | {"status": "not_quranic", "reason": "theme"}
    if not lines:
        return base | {"status": "unsure", "reason": "no_text"}
    if not set(styles) & RELIABLE_STYLES:
        return base | {"status": "unsure", "reason": "ornate_style"}
    best, hits = searcher().read(lines)
    if best is None or best.basmala or best.score < MIN_SCORE or best.qlen < MIN_LETTERS:
        return base | {"status": "unsure", "reason": "weak_match"}
    for h in hits:
        if h is not best and not h.basmala and h.qlen >= 8 and h.score >= 80 and not best.overlaps(h):
            return base | {"status": "unsure", "reason": "lines_disagree"}
    return base | {
        "status": "read",
        "reason": "ok",
        "sura": best.sura,
        "aya_from": best.aya_from,
        "aya_to": best.aya_to,
        "score": round(best.score, 1),
        "letters": best.qlen,
    }
