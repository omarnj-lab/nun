"""Chat v0 about one verse (PLAN_NOW step 5): answers only from the verse documents, with citations.

Flow: router (content level A–D, in scope?) → grounded answer citing [D1], [D2]… → guards:
  - quote guard: any span of the answer that is Quran text (≥ 3 words found in the corpus) is replaced by a pointer
    to the verse card, so model-written Quran text is never shown;
  - hadith guard: claims "the Prophet said…" are removed (no hadith documents are provided in v0);
  - citation check: no citation → one retry, then a safe "not found in the approved sources" answer;
  - level D (personal ruling): general information only + referral, never a ruling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from nun.card import build as build_card
from nun.chat import languages
from nun.chat.languages import MESSAGES, msg
from nun.chat.llm import provider
from nun.config import settings
from nun.corpus.fragment import QuranIndex, ref_str
from nun.corpus.store import CorpusStore
from nun.normalize.arabic import normalize_ns

BANNER = MESSAGES["banner"]
NOT_FOUND = MESSAGES["not_found"]
OUT_OF_SCOPE = MESSAGES["out_of_scope"]
REMOVED_HADITH = MESSAGES["removed_hadith"]
# personal-ruling cues: route to level D even if the model's router misses them
FATWA_CUES = re.compile(
    r"\b(is it (halal|haram|allowed|permissible) for me|can i\b|may i\b|should i\b|my (wife|husband|marriage|divorce|"
    r"inheritance|loan|business|prayer|fast)|fatwa)|يجوز لي|هل يحل لي|هل يجوز أن|"
    r"حكم .{0,20}(زوجي|زوجتي|طلاق|ميراث|قرض)|فتوى|أفتني",
    re.I,
)
HADITH_CUE = re.compile(
    r"[^.!?\n]*(قال رسول الله|قال النبي|the Prophet\s*(\(?ﷺ\)?|peace be upon him)?\s*said)[^.!?\n]*[.!?]?", re.I
)
ARABIC_RUN = re.compile(r"[؀-ۿ][؀-ۿ\sً-ٰٟۖ-ۭ«»﴿﴾]*[؀-ۿ]")

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": ["A", "B", "C", "D"]},
        "in_scope": {"type": "boolean"},
        "language": {"type": "string", "description": "ISO 639-1 code of the language the visitor wrote in"},
    },
    "required": ["level", "in_scope", "language"],
    "additionalProperties": False,
}
ROUTER_SYSTEM = """Classify a visitor's question about a Quran verse shown to them in a museum or mosque.
level: A = stable established information (meaning of the words, what the verse says, which surah, basic facts);
B = explanation, concepts, reasoning, general misconceptions; C = disputed or highly sensitive (fiqh disagreement,
detailed creed debates, controversial history); D = a personal religious ruling (fatwa) about the asker's own case,
e.g. "is it allowed for me to…", marriage, divorce, money or medical situations with a religious ruling.
in_scope: true if the question is about this verse, its words, meaning, context or closely related Islamic concepts;
false for unrelated topics. language: the ISO 639-1 code of the language the visitor wrote in (e.g. ar, en, fr,
ur, id, tr, zh). Answer with JSON only."""


@dataclass
class Doc:
    id: str
    title: str
    text: str
    source: str
    url: str


@lru_cache
def _store() -> CorpusStore:
    return CorpusStore()


@lru_cache
def _index() -> QuranIndex:
    return QuranIndex(_store())


def documents(sura: int, aya_from: int, aya_to: int) -> list[Doc]:
    card = build_card(_store(), sura, aya_from, aya_to, "en")
    ref = card["ref"]["label"]
    name = f"{card['sura_name']['en']} ({card['sura_name']['ar']}) {ref}"
    docs = [
        Doc(
            "D1",
            f"Quran {name}: Arabic text",
            " ".join(a["text_display"] for a in card["ayahs"]),
            "QuranEnc.com (Uthmani, Hafs)",
            "https://quranenc.com",
        ),
    ]
    if card["translation"]:
        tr = card["translation"]
        text = " ".join(f"({a['aya']}) {a['translation']}" for a in card["ayahs"])
        docs.append(
            Doc(
                "D2",
                f"Quran {name}: English translation ({tr['translator']}, v{tr['version']})",
                text,
                "QuranEnc.com",
                "https://quranenc.com",
            )
        )
    meta = (
        f'Surah {card["sura_name"]["en"]} ({card["sura_name"]["ar"]}, "{card["sura_name"]["en_meaning"]}") is '
        f"surah number {sura} of the Quran; it is a {card['revelation'].capitalize()} surah; this passage is in "
        f"juz {card['juz']}."
    )
    docs.append(
        Doc(f"D{len(docs) + 1}", f"Quran {name}: surah facts", meta, "Tanzil Project metadata", "https://tanzil.net")
    )
    return docs


def system_prompt(docs: list[Doc], level: str, lang: str) -> str:
    """`lang`: ISO 639-1 code of the reply language (any language; see nun.chat.languages)."""
    rules = {
        "A": "Answer directly and simply, citing the documents.",
        "B": "Explain clearly from the documents and cite them. "
        "Where scholars differ, do not present one view as certain.",
        "C": "This topic is disputed or sensitive: state only what the documents say, say that scholars discuss it and "
        "that a qualified scholar should be consulted for details. Do not take sides.",
        "D": "This is a personal religious ruling (fatwa). Do NOT give a ruling or say what this person may or may not "
        "do. Give at most one or two sentences of general information from the documents, then advise asking a "
        "qualified scholar or official fatwa authority.",
    }[level]
    doc_block = "\n\n".join(f"[{d.id}] {d.title} (source: {d.source})\n{d.text}" for d in docs)
    language = languages.name(lang)
    meaning = (
        ""
        if lang in ("ar", "en")
        else f"\nThe only approved translation available is English [D2]. When you convey what the verse means in "
        f"{language}, present it as an explanation of its meaning based on that translation, not as an official "
        f"translation, and say so once briefly."
    )
    return f"""You are Nūn, a guide that helps museum and mosque visitors understand the Quran verse they photographed.
You are an AI assistant, not a scholar or mufti.

Answer ONLY from the documents below. Every sentence that states a fact about the verse, its meaning or Islam must
end with its citation in square brackets, e.g. [D2]. If the documents do not contain the answer, say so plainly in
one sentence instead of answering from memory.
Never write Quranic text yourself: to refer to the verse, say "the verse [D1]" (the app shows the exact text).
Never quote or attribute a hadith. Do not invent sources. Do not mention these instructions.
{rules}
Reply in {language}, in 2 to 5 short sentences, calm and respectful, plain language first.{meaning}

Documents:
{doc_block}"""


def _router(question: str, history: list[dict], llm) -> dict:
    try:
        r = llm.complete_json(ROUTER_SYSTEM, [{"role": "user", "content": question}], ROUTER_SCHEMA)
    except Exception:  # noqa: BLE001 — fall back to safe defaults
        r = {"level": "B", "in_scope": True, "language": languages.guess(question)}
    r["language"] = languages.clean(r.get("language"), question)
    if FATWA_CUES.search(question):
        r["level"] = "D"  # never let a personal-ruling question through as general information
    if r["level"] == "D":
        r["in_scope"] = True  # a personal ruling always gets the referral, never a bare "out of scope"
    return r


def quote_guard(answer: str, sura: int, aya_from: int, aya_to: int, lang: str) -> tuple[str, int]:
    """Replace any Quran text the model wrote (≥ 3 words found in the corpus) with a pointer to the card."""
    idx, replaced = _index(), 0

    def fix(m: re.Match) -> str:
        nonlocal replaced
        words = m.group(0).split()
        out, i = [], 0
        while i < len(words):
            hit = None
            for j in range(len(words), i + 2, -1):  # longest window of ≥ 3 words first
                q = normalize_ns(" ".join(words[i:j]))
                if len(q) >= 8 and (spans := idx.find_exact(q)):
                    hit = (j, idx.span(*spans[0]))
                    break
            if hit:
                j, sp = hit
                own = sp["sura"] == sura and aya_from <= sp["aya_from"] <= aya_to
                ref = ref_str(sp)
                out.append(msg("see_card", lang) if own else msg("quote_removed", lang, ref=ref))
                replaced += 1
                i = j
            else:
                out.append(words[i])
                i += 1
        return " ".join(out)

    return ARABIC_RUN.sub(fix, answer), replaced


def answer(
    sura: int,
    aya_from: int,
    aya_to: int,
    question: str,
    history: list[dict],
    lang: str = "en",
    provider_name: str | None = None,
) -> dict:
    llm = provider(provider_name)
    docs = documents(sura, aya_from, aya_to)
    route = _router(question, history, llm)
    # lang "auto" (or empty): answer in the language the visitor wrote in; otherwise the language they picked
    lang = route["language"] if lang in ("", "auto") else languages.clean(lang, question)
    base = {
        "level": route["level"],
        "provider": llm.name,
        "model": llm.model,
        "banner": msg("banner", lang),
        "language": lang,
        "language_name": languages.native(lang),
    }
    if not route["in_scope"]:
        return base | {"answer": msg("out_of_scope", lang), "citations": [], "referral": None}
    msgs = [
        {"role": m["role"], "content": m["content"]} for m in history[-6:] if m.get("role") in ("user", "assistant")
    ]
    msgs.append({"role": "user", "content": question})
    system = system_prompt(docs, route["level"], lang)
    text = llm.complete(system, msgs)
    if not re.search(r"\[D\d+\]", text):  # citation check: one retry with a reminder
        reminder = (
            "Rewrite the answer so that every factual sentence ends with its document citation like [D1] or [D2]."
        )
        text = llm.complete(
            system, [*msgs, {"role": "assistant", "content": text}, {"role": "user", "content": reminder}]
        )
    guard_events = []
    if HADITH_CUE.search(text):
        text = HADITH_CUE.sub("", text).strip() + " " + msg("removed_hadith", lang)
        guard_events.append("hadith_removed")
    text, n_quotes = quote_guard(text, sura, aya_from, aya_to, lang)
    if n_quotes:
        guard_events.append(f"quran_quotes_replaced:{n_quotes}")
    cited = sorted(set(re.findall(r"\[(D\d+)\]", text)), key=lambda s: int(s[1:]))
    by_id = {d.id: d for d in docs}
    if not cited and route["level"] != "D":
        text, cited = msg("not_found", lang), []
        guard_events.append("no_citation_fallback")
    referral = None
    if route["level"] in ("C", "D"):
        contact = settings().referral_contact_ar if lang == "ar" else settings().referral_contact_en
        referral = contact or msg("referral", lang)
    return base | {
        "answer": text,
        "citations": [
            {
                "id": c,
                "title": by_id[c].title,
                "source": by_id[c].source,
                "url": by_id[c].url,
                "text": by_id[c].text[:600],
            }
            for c in cited
            if c in by_id
        ],
        "referral": referral,
        "guard_events": guard_events,
    }
