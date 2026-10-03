"""Verse card (PLAN_NOW step 4): everything comes from the verified corpus, nothing is generated.

Quran text = QuranEnc Uthmani, verbatim; translation = the approved one for the language (English today); recitation
= human reciter per ayah (EveryAyah, Mishary Alafasy), streamed from the source.
"""

from __future__ import annotations

from nun.corpus.sources import TRANSLATIONS
from nun.corpus.store import CorpusStore

RECITER = {"name": "Mishary Rashid Alafasy", "source": "EveryAyah.com", "url": "https://everyayah.com"}


def ref_label(sura: int, aya_from: int, aya_to: int) -> str:
    return f"{sura}:{aya_from}" + (f"-{aya_to}" if aya_to != aya_from else "")


def build(store: CorpusStore, sura: int, aya_from: int, aya_to: int | None = None, lang: str = "en") -> dict:
    aya_to = aya_to or aya_from
    recs = store.range(sura, aya_from, aya_to)  # KeyError for a reference that does not exist
    first = recs[0]
    ayahs, translation_meta = [], None
    for r in recs:
        tr = store.translation(r.sura, r.aya, lang) or store.translation(r.sura, r.aya, "en")
        if tr:
            key, t = tr
            translation_meta = {
                "lang": t.lang,
                "key": key,
                "translator": TRANSLATIONS[key]["translator"],
                "version": t.version,
                "source": "QuranEnc.com",
            }
        ayahs.append(
            {
                "aya": r.aya,
                "text_uthmani": r.text_uthmani,  # verbatim; never re-normalised or generated
                "translation": tr[1].text if tr else None,
                "footnotes": tr[1].footnotes if tr else None,
                "audio": r.audio["alafasy"],
            }
        )
    return {
        "ref": {"sura": sura, "aya_from": aya_from, "aya_to": aya_to, "label": ref_label(sura, aya_from, aya_to)},
        "sura_name": {"ar": first.sura_name_ar, "en": first.sura_name_en, "en_meaning": first.sura_name_en_meaning},
        "juz": first.juz,
        "revelation": first.revelation,
        "ayahs": ayahs,
        "translation": translation_meta,
        "tafsir": None,  # no tafsir is approved yet (SOURCES.md §1); shown once the team approves one
        "recitation": RECITER,
        "sources": [
            {"label": "Quran text (Uthmani, Hafs) and translation: QuranEnc.com", "url": "https://quranenc.com"},
            {"label": "Text cross-checked with the Tanzil Project", "url": "https://tanzil.net"},
            {"label": "Recitation: Mishary Rashid Alafasy via EveryAyah.com", "url": "https://everyayah.com"},
        ],
    }
