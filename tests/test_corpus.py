"""Corpus integrity tests; skipped until `make corpus` has built data/corpus/quran.jsonl."""

from pathlib import Path

import pytest

from nun.corpus.sources import TRANSLATIONS
from nun.corpus.store import CorpusStore
from nun.normalize.arabic import normalize

CORPUS = Path("data/corpus/quran.jsonl")
pytestmark = pytest.mark.skipif(not CORPUS.exists(), reason="run `make corpus` first")


@pytest.fixture(scope="module")
def store() -> CorpusStore:
    return CorpusStore(CORPUS)


def test_counts(store: CorpusStore) -> None:
    assert len(store) == 6236
    assert len({r.sura for r in store.all()}) == 114


def test_known_ayah(store: CorpusStore) -> None:
    r = store.get(20, 114)
    assert r.sura_name_ar == "طه" and r.juz == 16 and r.revelation == "meccan"
    assert "وقل رب زدني علما" in r.text_norm
    assert r.audio["alafasy"].endswith("/020114.mp3")


def test_ayat_al_kursi_is_medinan_juz_3(store: CorpusStore) -> None:
    r = store.get(2, 255)
    assert r.revelation == "medinan" and r.juz == 3
    assert r.text_norm.startswith(normalize("الله لا إله إلا هو الحي القيوم"))


def test_basmala_header_not_in_aya_1(store: CorpusStore) -> None:
    assert store.get(2, 1).text_norm == "الم"
    assert store.get(112, 1).text_norm == "قل هو الله احد"
    assert store.get(1, 1).text_norm == "بسم الله الرحمن الرحيم"  # al-Fatiha: the Basmala is ayah 1
    assert "بسم الله الرحمن الرحيم" in store.get(27, 30).text_norm  # the Basmala inside Surat an-Naml
    assert not store.get(9, 1).text_norm.startswith("بسم")
    basmala_ayahs = [r.id for r in store.all() if "بسم الله الرحمن الرحيم" in r.text_norm]
    assert basmala_ayahs == ["q:1:1", "q:27:30"]


def test_range_and_missing(store: CorpusStore) -> None:
    assert [r.aya for r in store.range(112, 1, 4)] == [1, 2, 3, 4]
    with pytest.raises(KeyError):
        store.get(1, 8)


def test_only_approved_translations_are_served(store: CorpusStore) -> None:
    approved_langs = {i["lang"] for i in TRANSLATIONS.values() if i["status"] == "approved"}
    assert approved_langs == {"en"}  # update when the reviewer approves fr/ur/id/zh (SOURCES.md §1)
    assert store.translation(1, 1, "en")[0] == "english_saheeh"
    for lang in {"fr", "ur", "id", "zh"}:
        assert store.translation(1, 1, lang) is None
    assert store.tafsir(1, 1) is None  # tafsir decision still open (SOURCES.md §1)
