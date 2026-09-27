"""M1 reviewer drafts → data/lists/{names.draft.jsonl, dhikr.draft.jsonl, inscriptions.draft.yaml}.

Nothing here is authoritative. Every entry is status "draft" with reviewed_by = null until the Sharia reviewer
signs it off in docs/REVIEW_LOG.md. What this script DOES verify, by machine, against data/corpus/quran.jsonl:
  - whether each Name / phrase occurs verbatim (normalised) in the Quran, and where;
  - the Quran reference of every DuwatBench "quranic" inscription (exact, then fuzzy).
What it does NOT verify: hadith references, gradings, meanings. Those are left empty or marked
`verified: false` with a dorar.net search link for the reviewer. Never ship an unverified entry.
"""

from __future__ import annotations

import json
import urllib.parse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from nun.corpus.store import CorpusStore
from nun.normalize.arabic import normalize, normalize_ns

OUT = Path("data/lists")

# The enumeration commonly inscribed as "the 99 Names": the list appended to the hadith in Jami' at-Tirmidhi
# (Da'awat, no. 3507). The hadith "إن لله تسعة وتسعين اسمًا" itself is in al-Bukhari and Muslim WITHOUT a list;
# many scholars consider the enumeration a narrator's addition. The reviewer decides how to present this.
NAMES_TIRMIDHI = (
    "الرحمن الرحيم الملك القدوس السلام المؤمن المهيمن العزيز الجبار المتكبر الخالق البارئ المصور الغفار القهار "
    "الوهاب الرزاق الفتاح العليم القابض الباسط الخافض الرافع المعز المذل السميع البصير الحكم العدل اللطيف الخبير "
    "الحليم العظيم الغفور الشكور العلي الكبير الحفيظ المقيت الحسيب الجليل الكريم الرقيب المجيب الواسع الحكيم "
    "الودود المجيد الباعث الشهيد الحق الوكيل القوي المتين الولي الحميد المحصي المبدئ المعيد المحيي المميت الحي "
    "القيوم الواجد الماجد الواحد الأحد الصمد القادر المقتدر المقدم المؤخر الأول الآخر الظاهر الباطن الوالي المتعالي "
    "البر التواب المنتقم العفو الرؤوف مالك_الملك ذو_الجلال_والإكرام المقسط الجامع الغني المغني المانع الضار "
    "النافع النور الهادي البديع الباقي الوارث الرشيد الصبور"
).split()

# Common non-Quranic (or partly Quranic) inscriptions. hadith = unverified candidate from memory, for the reviewer
# to confirm or replace on dorar.net; None = no candidate offered.
DHIKR = [
    ("shahada", "لا إله إلا الله محمد رسول الله", None),
    ("shahadatan", "أشهد أن لا إله إلا الله وأشهد أن محمدا عبده ورسوله", None),
    ("tahlil", "لا إله إلا الله", None),
    (
        "tahlil-full",
        "لا إله إلا الله وحده لا شريك له له الملك وله الحمد وهو على كل شيء قدير",
        ("Sahih al-Bukhari", "6403"),
    ),
    ("tasbih", "سبحان الله", None),
    ("subhanallah-wabihamdih", "سبحان الله وبحمده", ("Sahih Muslim", "2691")),
    ("kalimatan-khafifatan", "سبحان الله وبحمده سبحان الله العظيم", ("Sahih al-Bukhari", "6406")),
    ("baqiyat-salihat", "سبحان الله والحمد لله ولا إله إلا الله والله أكبر", ("Sahih Muslim", "2137")),
    ("tahmid", "الحمد لله", None),
    ("takbir", "الله أكبر", None),
    ("hawqala", "لا حول ولا قوة إلا بالله", ("Sahih al-Bukhari", "4205")),
    ("istighfar", "أستغفر الله", None),
    ("istighfar-full", "أستغفر الله العظيم وأتوب إليه", None),
    ("mashallah", "ما شاء الله", None),
    ("mashallah-la-quwwata", "ما شاء الله لا قوة إلا بالله", None),
    ("tabarakallah", "تبارك الله", None),
    ("hasbunallah", "حسبنا الله ونعم الوكيل", None),
    ("hasbiyallah", "حسبي الله ونعم الوكيل", None),
    ("tawakkul", "توكلت على الله", None),
    ("salat-ibrahimiyya", "اللهم صل على محمد وعلى آل محمد", ("Sahih al-Bukhari", "3370")),
    ("salla-allahu-alayhi", "صلى الله عليه وسلم", None),
    ("ya-hayy-ya-qayyum", "يا حي يا قيوم", None),
    ("ya-allah", "يا الله", None),
    ("allah-jalla-jalaluh", "الله جل جلاله", None),
    ("la-ghalib", "لا غالب إلا الله", None),
    ("al-mulk-lillah", "الملك لله", None),
    ("al-izza-lillah", "العزة لله", None),
    ("hadha-min-fadl", "هذا من فضل ربي", None),
    ("wa-ma-tawfiqi", "وما توفيقي إلا بالله", None),
    ("inna-lillah", "إنا لله وإنا إليه راجعون", None),
    ("radiya-allahu-anhu", "رضي الله عنه", None),
    ("bismillah-short", "بسم الله", None),
]

# SPEC §6.1 canonical inscription verses: (sura, aya_from, aya_to)
CANONICAL = [
    (1, 1, 7),
    (2, 255, 255),
    (2, 285, 286),
    (3, 18, 19),
    (3, 26, 26),
    (9, 40, 40),
    (13, 28, 28),
    (17, 80, 80),
    (20, 114, 114),
    (24, 35, 35),
    (33, 56, 56),
    (39, 53, 53),
    (48, 1, 1),
    (48, 29, 29),
    (55, 13, 13),
    (61, 13, 13),
    (68, 4, 4),
    (94, 5, 6),
    (112, 1, 4),
    (113, 1, 5),
    (114, 1, 6),
]


@dataclass
class Word:
    sura: int
    aya: int
    simple: str
    ns: str


class QuranIndex:
    """Whole-Quran no-space string with char → word mapping, for exact fragment location."""

    def __init__(self, store: CorpusStore) -> None:
        self.words: list[Word] = []
        chars, owner = [], []
        for r in store.all():
            for w in r.text_simple.split():
                ns = normalize_ns(w)
                if not ns:
                    continue
                self.words.append(Word(r.sura, r.aya, w, ns))
                chars.append(ns)
                owner.extend([len(self.words) - 1] * len(ns))
        self.concat = "".join(chars)
        self.owner = owner
        self.word_start = {i for i, w in enumerate(owner) if i == 0 or owner[i - 1] != w}
        # per-ayah windows (1–3 consecutive ayahs within a sura) for fuzzy search
        self.ayahs = store.all()

    def find_exact(self, query_ns: str, whole_words: bool = True) -> list[tuple[int, int]]:
        """All occurrences as (first_word, last_word) index pairs."""
        hits, start = [], 0
        while (i := self.concat.find(query_ns, start)) != -1:
            j = i + len(query_ns) - 1
            end_ok = j + 1 == len(self.concat) or (j + 1) in self.word_start
            if not whole_words or (i in self.word_start and end_ok):
                hits.append((self.owner[i], self.owner[j]))
            start = i + 1
        return hits

    def span(self, w0: int, w1: int) -> dict:
        a, b = self.words[w0], self.words[w1]
        return {
            "sura": a.sura,
            "aya_from": a.aya,
            "aya_to": b.aya,
            "fragment": " ".join(w.simple for w in self.words[w0 : w1 + 1]),
            "cross_sura": a.sura != b.sura,
        }


def ref_str(sp: dict) -> str:
    return f"{sp['sura']}:{sp['aya_from']}" + (f"-{sp['aya_to']}" if sp["aya_to"] != sp["aya_from"] else "")


def quran_occurrences(idx: QuranIndex, text: str) -> list[str]:
    return sorted({ref_str(idx.span(*h)) for h in idx.find_exact(normalize_ns(text))}, key=_ref_key)


def _ref_key(r: str) -> tuple[int, int]:
    s, a = r.split(":")
    return int(s), int(a.split("-")[0])


def build_names(idx: QuranIndex) -> list[dict]:
    assert len(NAMES_TIRMIDHI) == 99, len(NAMES_TIRMIDHI)
    rows = [{"id": "n:allah", "text": "الله", "list": "the Name"}]
    rows += [
        {"id": f"n:{i:02d}", "text": n.replace("_", " "), "list": "tirmidhi-3507"}
        for i, n in enumerate(NAMES_TIRMIDHI, 1)
    ]
    out = []
    for r in rows:
        occ = quran_occurrences(idx, r["text"])
        bare = r["text"].removeprefix("ال") if r["text"].startswith("ال") and " " not in r["text"] else None
        occ_bare = quran_occurrences(idx, bare) if bare and r["text"] != "الله" else []
        out.append(
            {
                **r,
                "type": "name",
                "text_norm": normalize(r["text"]),
                "quran_as_written": {"count": len(occ), "refs": occ[:5]},
                "quran_without_al": {"text": bare, "count": len(occ_bare), "refs": occ_bare[:5]} if bare else None,
                "meaning": None,  # pending: from an approved source (Jamhara dictionary / reviewer), never generated
                "source": {"enumeration": "Jami' at-Tirmidhi 3507 (commonly printed list)", "verified": False},
                "status": "draft",
                "reviewed_by": None,
            }
        )
    return out


def build_dhikr(idx: QuranIndex) -> list[dict]:
    out = []
    for key, text, hadith in DHIKR:
        occ = quran_occurrences(idx, text)
        out.append(
            {
                "id": f"d:{key}",
                "type": "dhikr",
                "text": text,
                "text_norm": normalize(text),
                "quran_verbatim_refs": occ,  # non-empty → the scan pipeline must treat it as (part of) a verse
                "hadith_candidate": (
                    {"book": hadith[0], "number": hadith[1], "grading": None, "verified": False} if hadith else None
                ),
                "dorar_search": "https://dorar.net/hadith/search?q=" + urllib.parse.quote(text),
                "status": "draft",
                "reviewed_by": None,
            }
        )
    return out


def locate_fuzzy(idx: QuranIndex, q_ns: str) -> tuple[dict, float] | None:
    """Best fragment inside a 1–3-ayah window (same sura) by partial_ratio_alignment → (exact word span, score).

    The aligned character range is mapped back to corpus words, so the span covers only what matched.
    """
    grams = {q_ns[i : i + 3] for i in range(len(q_ns) - 2)}
    # char range of each ayah in idx.concat
    bounds: list[tuple[int, int, int]] = []  # (sura, char_start, char_end)
    pos = 0
    ayah_chars: dict[tuple[int, int], list[int]] = {}
    for w in idx.words:
        r = ayah_chars.setdefault((w.sura, w.aya), [pos, pos])
        pos += len(w.ns)
        r[1] = pos
    keys = list(ayah_chars)
    windows = []
    for i, (s, _a) in enumerate(keys):
        for k in (1, 2, 3):
            if i + k > len(keys) or keys[i + k - 1][0] != s:
                break
            c0, c1 = ayah_chars[keys[i]][0], ayah_chars[keys[i + k - 1]][1]
            windows.append((c0, c1, k))
    bounds = sorted(windows, key=lambda w: -sum(g in idx.concat[w[0] : w[1]] for g in grams))[:60]
    best = None
    for c0, c1, k in bounds:
        al = fuzz.partial_ratio_alignment(q_ns, idx.concat[c0:c1])
        rank = (round(al.score, 1), -k)  # higher score first, then the smallest window
        if best is None or rank > best[0]:
            best = (rank, c0 + al.dest_start, c0 + al.dest_end - 1, al.score)
    if not best:
        return None
    _, g0, g1, score = best
    return idx.span(idx.owner[g0], idx.owner[g1]), score


def build_inscriptions(idx: QuranIndex, store: CorpusStore) -> tuple[list[dict], list[dict]]:
    entries: dict[tuple, dict] = {}

    def add(sp: dict, source: str, match: str, all_refs: list[str], score: float | None = None) -> None:
        key = (sp["sura"], sp["aya_from"], sp["aya_to"], sp.get("fragment"))
        e = entries.setdefault(
            key,
            {
                "ref": ref_str(sp),
                "sura": sp["sura"],
                "aya_from": sp["aya_from"],
                "aya_to": sp["aya_to"],
                "fragment": sp.get("fragment"),
                "sources": Counter(),
                "match": match,
                "score": score,
                "also_occurs_at": [r for r in all_refs if r != ref_str(sp)],
                "status": "draft",
                "reviewed_by": None,
            },
        )
        e["sources"][source] += 1

    for s, a0, a1 in CANONICAL:
        frag = " ".join(r.text_simple for r in store.range(s, a0, a1))
        add({"sura": s, "aya_from": a0, "aya_to": a1, "fragment": frag}, "canonical", "exact", [])
    basmala = {"sura": 1, "aya_from": 1, "aya_to": 1, "fragment": store.get(1, 1).text_simple}
    add(basmala, "canonical:basmala-alone", "exact", quran_occurrences(idx, basmala["fragment"]))

    from datasets import load_dataset

    ds = load_dataset("MBZUAI/DuwatBench", split="train").remove_columns(["image"])
    unmatched = []
    quranic = [r for r in ds if r["category"] == "quranic"]
    basmala_ns = normalize_ns(store.get(1, 1).text_simple)
    for row in quranic:
        texts = [" ".join(row["text"])] + (list(row["text"]) if len(row["text"]) > 1 else [])
        # a Basmala written above another verse: also try the rest on its own
        texts += [
            t[len(basmala_ns) :] for t in map(normalize_ns, texts) if t.startswith(basmala_ns) and t != basmala_ns
        ]
        placed = False
        for t in texts:
            q_ns = normalize_ns(t)
            if len(q_ns) < 2:
                continue
            # partial-word matches only for longer text (a 2–7 letter partial hit is meaningless)
            hits = idx.find_exact(q_ns) or (idx.find_exact(q_ns, whole_words=False) if len(q_ns) >= 8 else [])
            hits = [h for h in hits if not idx.span(*h)["cross_sura"]]
            if hits:
                spans = [idx.span(*h) for h in hits]
                refs = sorted({ref_str(sp) for sp in spans}, key=_ref_key)
                add(spans[0], "duwatbench", "exact" if len(refs) == 1 else "exact-ambiguous", refs)
                placed = True
                break
        if not placed:
            q_ns = normalize_ns(texts[0])
            got = locate_fuzzy(idx, q_ns) if len(q_ns) >= 8 else None
            if got and got[1] >= 90:
                add(got[0], "duwatbench", "fuzzy", [], round(got[1], 1))
            else:
                unmatched.append(
                    {
                        "image_id": row["image_id"],
                        "gold_text": " / ".join(row["text"]),
                        "best_guess": ref_str(got[0]) if got else None,
                        "score": round(got[1], 1) if got else None,
                        "reason": "too short" if len(q_ns) < 8 else "no confident match",
                    }
                )
    out = []
    for e in entries.values():
        e["sources"] = dict(e["sources"])
        out.append(e)
    out.sort(key=lambda e: (e["sura"], e["aya_from"], e["aya_to"], e["fragment"] or ""))
    return out, unmatched


def main() -> None:
    store = CorpusStore()
    idx = QuranIndex(store)
    OUT.mkdir(parents=True, exist_ok=True)
    names = build_names(idx)
    dhikr = build_dhikr(idx)
    inscriptions, unmatched = build_inscriptions(idx, store)
    for name, rows in (("names.draft.jsonl", names), ("dhikr.draft.jsonl", dhikr)):
        (OUT / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    header = "# DRAFT for Sharia review (M1). Generated by scripts/build_lists.py; do not hand-edit, regenerate.\n"
    (OUT / "inscriptions.draft.yaml").write_text(
        header
        + yaml.safe_dump(
            {"spans": inscriptions, "unmatched_duwatbench": unmatched}, allow_unicode=True, sort_keys=False
        ),
        encoding="utf-8",
    )
    by_match = Counter(e["match"] for e in inscriptions)
    print(f"names: {len(names)} (in Quran as written: {sum(1 for n in names if n['quran_as_written']['count'])})")
    print(f"dhikr: {len(dhikr)} (verbatim in Quran: {sum(1 for d in dhikr if d['quran_verbatim_refs'])})")
    print(f"inscription spans: {len(inscriptions)} {dict(by_match)}; DuwatBench unmatched: {len(unmatched)}")
    by_ref = defaultdict(int)
    for e in inscriptions:
        by_ref[e["sura"]] += 1
    print("top suras:", sorted(by_ref.items(), key=lambda x: -x[1])[:8])


if __name__ == "__main__":
    main()
