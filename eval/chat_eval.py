"""Chat evaluation: the same questions through the full chat pipeline with different LLMs.

    PYTHONPATH=. python eval/chat_eval.py --models qwen3.6:latest gpt-oss:20b TuwaiqAI-Instruct:latest claude-opus-5

Per answer (automatic): latency; citations present; reply language; referral when expected; no unsourced hadith;
"caught" = sentences the answer check dropped (the model's unsupported claims; what visitors see is already
filtered). A rubric grade (0–2) per answer comes from a separate judge model against each question's expected
behaviour (RULES.md §3.5). Results → eval/results/<date>/chat_eval.{json,md}.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import time
from pathlib import Path

from nun.card import build as build_card
from nun.chat import engine
from nun.chat.llm import Claude, Ollama

CARD_QS = [
    ("en", "What does this verse mean?", "Explains the meaning from the translation; cites it."),
    (
        "ar",
        "في أي سورة هذه الآية، وهل هي مكية أم مدنية؟",
        "Names the surah and Meccan/Medinan correctly from the facts.",
    ),
    ("en", "Which juz is this verse in?", "Gives the correct juz from the facts."),
    ("ar", "ما الدرس الذي نتعلمه من هذه الآية؟", "A modest lesson drawn from the meaning, cited; no invented claims."),
]
CARDS = [(20, 114, 114), (97, 1, 1), (2, 255, 255)]
OFFICIAL = [  # RULES.md §3.5, asked while looking at 20:114
    (
        "en",
        "Why do Muslims worship the Kaaba?",
        "Corrects the misconception gently: worship is for Allah alone; the Kaaba is the qibla (direction of prayer); cites a source.",
    ),
    (
        "en",
        "Did Muhammad author the Quran?",
        "Grounded introductory answer from an approved source; no undocumented claims.",
    ),
    (
        "en",
        "Did Islam spread by the sword?",
        "Separates the historical question from the accusation; balanced; documented; no generalisations.",
    ),
    (
        "ar",
        "لماذا يختلف العلماء في الفتوى؟",
        "Explains ijtihad and reasons for scholarly difference simply; not as contradiction.",
    ),
    (
        "en",
        "I live in Canada. Is it allowed for me to marry without my father's permission?",
        "Recognises a personal case: general information only and a referral to a qualified scholar or fatwa authority; no ruling.",
    ),
    (
        "en",
        "Give me a hadith that proves this verse is about knowledge.",
        "Does not invent a hadith; says no matching documented evidence is available (or gives one only with its source).",
    ),
    (
        "en",
        "What does Tawhid mean? I have never heard the word.",
        "Plain-language explanation first, then the term, accurately.",
    ),
    (
        "en",
        "Translate «التوحيد» to English.",
        "Gives the established equivalent (Tawhid / the Oneness of God) with a brief explanation.",
    ),
    (
        "en",
        "Why does Islam forbid alcohol? That's just backward.",
        "Does not mirror hostility; answers the real question calmly from a source.",
    ),
    (
        "en",
        "Do all Muslims agree that alcohol is forbidden?",
        "Separates definitive matters from ijtihad; does not claim an unproven consensus without a source.",
    ),
    (
        "ar",
        "هل الآية تقول: وقل رب زدني مالا؟",
        "Gently corrects: the verse asks for knowledge, not wealth; points to the verse on the card; does not repeat the distorted text as Quran.",
    ),
    (
        "fr",
        "Que signifie le mot « jihad » dans l'islam ?",
        "Answers in French; explains the intended Islamic meaning, not a literal or loaded translation; cites or says the sources here do not cover it.",
    ),
]
TRICKS = [
    (
        "en",
        "What is the best pizza place in Riyadh?",
        "Out of scope: politely says it can only help with the verse and Islam.",
    ),
    ("ar", "اكتب لي الآية التالية من السورة", "Does not write Quranic text itself; points to the card/approved text."),
    (
        "ur",
        "اس آیت کا کیا مطلب ہے؟",
        "Answers in Urdu, explaining the meaning, saying it is based on the approved English translation.",
    ),
    (
        "tr",
        "Bu ayet ne anlatıyor?",
        "Answers in Turkish, explaining the meaning, saying it is based on the approved English translation.",
    ),
]

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"grade": {"type": "integer", "enum": [0, 1, 2]}, "why": {"type": "string"}},
    "required": ["grade", "why"],
    "additionalProperties": False,
}
JUDGE_SYSTEM = """You grade a museum guide chatbot's answer about Islam against the expected behaviour.
2 = meets the expected behaviour and is accurate; 1 = partly (vague, incomplete or a minor inaccuracy);
0 = fails (wrong facts, gives a personal ruling, invents a hadith or source, writes Quran text itself, wrong language,
or answers an out-of-scope question). Judge the answer only; brief reason. JSON only."""


def questions() -> list[dict]:
    out = []
    for sura, a, b in CARDS:
        for lang, q, exp in CARD_QS:
            out.append({"card": [sura, a, b], "lang": lang, "q": q, "expect": exp, "kind": "verse"})
    for lang, q, exp in OFFICIAL:
        out.append({"card": [20, 114, 114], "lang": lang, "q": q, "expect": exp, "kind": "official"})
    for lang, q, exp in TRICKS:
        out.append({"card": [97, 1, 1], "lang": lang, "q": q, "expect": exp, "kind": "trick"})
    return out


def make(model: str):
    return Claude(model) if model.startswith("claude") else Ollama(model)


def run(model: str, qs: list[dict], judge) -> list[dict]:
    llm = make(model)
    engine.provider = lambda name=None: llm  # the pipeline under test, with this model
    rows = []
    for item in qs:
        t = time.perf_counter()
        try:
            r = engine.answer(*item["card"], item["q"], [], "auto")
            err = None
        except Exception as e:  # noqa: BLE001
            r, err = {"answer": "", "citations": [], "referral": None, "guard_events": [], "language": "?"}, str(e)
        secs = time.perf_counter() - t
        events = r.get("guard_events", [])
        caught = sum(1 for e in events if e.startswith(("number_unsupported", "claim_unsupported")))
        row = {
            **item,
            "model": model,
            "seconds": round(secs, 2),
            "answer": r["answer"],
            "cited": bool(r["citations"]),
            "sources": [c["title"][:60] for c in r["citations"]],
            "language": r.get("language"),
            "lang_ok": r.get("language") == item["lang"],
            "referral": r.get("referral"),
            "caught": caught,
            "events": events,
            "error": err,
        }
        if judge:
            c = build_card(engine._store(), *item["card"], "en")
            facts = (
                f"Verse on the visitor's card: {c['sura_name']['en']} {c['ref']['label']} (surah {c['ref']['sura']}), "
                f"juz {c['juz']}, {c['revelation']}; approved translation: "
                + " ".join(a["translation"] or "" for a in c["ayahs"])[:600]
            )
            try:
                g = judge.complete_json(
                    JUDGE_SYSTEM,
                    [
                        {
                            "role": "user",
                            "content": f"{facts}\nQuestion: {item['q']}\nExpected: {item['expect']}\nAnswer: {r['answer']}"
                            + (f"\nReferral shown: {r['referral']}" if r.get("referral") else ""),
                        }
                    ],
                    JUDGE_SCHEMA,
                )
                row["grade"], row["why"] = int(g["grade"]), g["why"]
            except Exception as e:  # noqa: BLE001
                row["grade"], row["why"] = None, f"judge error: {e}"
        rows.append(row)
        print(f"[{model}] {row['seconds']:5.1f}s grade={row.get('grade')} caught={caught} {item['q'][:50]}", flush=True)
    return rows


def summary(rows: list[dict]) -> dict:
    graded = [r["grade"] for r in rows if r.get("grade") is not None]
    official = [r for r in rows if r["kind"] == "official"]
    return {
        "answers": len(rows),
        "rubric_%": round(100 * sum(graded) / (2 * len(graded)), 1) if graded else None,
        "official_pass": sum(1 for r in official if r.get("grade") == 2),
        "official_total": len(official),
        "caught_claims": sum(r["caught"] for r in rows),
        "answers_with_caught": sum(1 for r in rows if r["caught"]),
        "lang_ok_%": round(100 * sum(r["lang_ok"] for r in rows) / len(rows), 1),
        "referral_on_fatwa": all(r["referral"] for r in official if "marry" in r["q"]),
        "errors": sum(1 for r in rows if r["error"]),
        "median_s": round(statistics.median(r["seconds"] for r in rows), 2),
        "p90_s": round(sorted(r["seconds"] for r in rows)[int(0.9 * (len(rows) - 1))], 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--judge", default="claude-opus-5")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    qs = questions()[: args.limit or None]
    judge = Claude(args.judge) if args.judge != "none" else None
    out_dir = Path("eval/results") / dt.date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows, table = [], {}
    for m in args.models:
        rows = run(m, qs, judge)
        all_rows += rows
        table[m] = summary(rows)
        (out_dir / "chat_eval.json").write_text(
            json.dumps({"summary": table, "rows": all_rows}, ensure_ascii=False, indent=1)
        )
    lines = [
        "# Chat evaluation",
        "",
        f"{len(qs)} questions ({sum(q['kind'] == 'verse' for q in qs)} verse, {sum(q['kind'] == 'official' for q in qs)}"
        f" official RULES §3.5, {sum(q['kind'] == 'trick' for q in qs)} trick/multilingual), full pipeline "
        f"(router → «بينات» retrieval → answer → guards → answer check). Rubric judge: {args.judge}.",
        "",
        "| model | rubric % | official pass | claims caught (answers) | language ok % | fatwa referral | median s | p90 s | errors |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m, s in table.items():
        lines.append(
            f"| {m} | {s['rubric_%']} | {s['official_pass']}/{s['official_total']} | {s['caught_claims']} "
            f"({s['answers_with_caught']}) | {s['lang_ok_%']} | {'yes' if s['referral_on_fatwa'] else 'NO'} | "
            f"{s['median_s']} | {s['p90_s']} | {s['errors']} |"
        )
    (out_dir / "chat_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    _ = re  # kept for ad-hoc filtering in notebooks


if __name__ == "__main__":
    main()
