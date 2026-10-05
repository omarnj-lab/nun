"""Answer checking: every sentence must be supported by the documents it cites, or it is dropped.

Two layers:
  1. numbers (deterministic): a number in a sentence must appear in the documents it cites (or in the verse
     reference); "juz 55" or "the 2nd surah" for 97 are caught without a model;
  2. support (model judge): one call lists the sentences whose claims the cited documents do not state.
Sentences that only point to the card, advise asking a scholar, or carry no factual claim are kept.
"""

from __future__ import annotations

import re

SENTENCE = re.compile(r"[^.!?؟。\n]+(?:[.!?؟。]+|\n|$)")
CITE = re.compile(r"\[(D\d+)\]")
NUMBER = re.compile(r"\d+")
JUZ_WORD = r"(?:juz'?|cüz(?:ü|ünde|de)?|الجزء|جزء|پارہ|پارے|juzuk|para|джуз|chapter-part)"
JUZ_NUM = re.compile(rf"{JUZ_WORD}\W{{0,3}}(\d+)|(\d+)\W{{0,3}}(?:\.|th|st|nd|rd)?\s*{JUZ_WORD}", re.I)
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"unsupported": {"type": "array", "items": {"type": "integer"}}},
    "required": ["unsupported"],
    "additionalProperties": False,
}
JUDGE_SYSTEM = """You check an assistant's answer against its source documents.
For each numbered sentence, decide whether every factual claim in it is stated in, or directly follows from, the
documents it cites (shown after the sentence). A sentence with no factual claim (a greeting, a pointer to the verse
on the card, advice to ask a scholar, a statement that the sources do not cover something) is supported.
A claim is unsupported if the cited documents do not contain it, contradict it, or the sentence cites nothing.
Return JSON {"unsupported": [sentence numbers]} only."""


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE.findall(text) if s.strip()]


def numbers_ok(sentence: str, cited_text: str, allowed: set[str]) -> bool:
    nums = NUMBER.findall(CITE.sub("", sentence).translate(ARABIC_DIGITS))
    pool = set(NUMBER.findall(cited_text.translate(ARABIC_DIGITS))) | allowed
    return all(n in pool for n in nums)


def juz_ok(sentence: str, juz: int | None) -> bool:
    """A number written next to "juz" (any of the visitor languages) must be the verse's juz."""
    if juz is None:
        return True
    plain = CITE.sub("", sentence).translate(ARABIC_DIGITS)
    return all(int(a or b) == juz for a, b in JUZ_NUM.findall(plain))


def check(
    text: str, docs: dict[str, str], allowed_numbers: set[str], judge, juz: int | None = None
) -> tuple[str, list[str]]:
    """→ (checked text, events). `docs`: id → text; `judge(system, user, schema)` → dict, or None to skip layer 2."""
    sents = sentences(text)
    if not sents:
        return text, []
    keep = [True] * len(sents)
    events = []
    for i, s in enumerate(sents):
        cited = " ".join(docs.get(c, "") for c in CITE.findall(s))
        if not numbers_ok(s, cited, allowed_numbers) or not juz_ok(s, juz):
            keep[i] = False
            events.append(f"number_unsupported:{i}")
    if judge is not None:
        lines = []
        for i, s in enumerate(sents):
            ids = CITE.findall(s)
            lines.append(f"{i}. {s}\n   cites: {', '.join(ids) or 'nothing'}")
        used = sorted({c for s in sents for c in CITE.findall(s)}, key=lambda c: int(c[1:]))
        doc_block = "\n\n".join(f"[{c}]\n{docs[c][:3500]}" for c in used if c in docs)
        try:
            verdict = judge(JUDGE_SYSTEM, f"Documents:\n{doc_block}\n\nSentences:\n" + "\n".join(lines), JUDGE_SCHEMA)
            for i in verdict.get("unsupported", []):
                if isinstance(i, int) and 0 <= i < len(sents) and keep[i]:
                    keep[i] = False
                    events.append(f"claim_unsupported:{i}")
        except Exception:  # noqa: BLE001 — the judge is a second line; numbers were already checked
            events.append("judge_unavailable")
    return " ".join(s for s, k in zip(sents, keep, strict=True) if k), events
