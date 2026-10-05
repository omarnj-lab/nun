"""The reading path's gate: a verse is shown only for a Quranic, reliably read (Naskh), consistent, strong reading."""

from pathlib import Path

import pytest

from nun import reading
from nun.retrieval.verse_search import searcher

pytestmark = pytest.mark.skipif(not Path("data/corpus/quran.jsonl").exists(), reason="run `make corpus` first")

KURSI = "الله لا اله الا هو الحي القيوم لا تأخذه سنة ولا نوم"


def analysis(text, styles=("Naskh",), theme="quranic"):
    return {"styles": list(styles), "theme": theme, "regions": [{"box": [0, 0, 1, 1], "text": t} for t in text]}


def test_search_finds_the_nearest_passage():
    hit = searcher().locate("وقل رب زدني علما")
    assert (hit.sura, hit.aya_from, hit.score) == (20, 114, 100.0)


def test_naskh_quranic_reading_is_shown():
    d = reading.decide(analysis([KURSI]))
    assert d["status"] == "read" and (d["sura"], d["aya_from"]) == (2, 255)


def test_not_quranic_theme_shows_no_verse():
    assert reading.decide(analysis([KURSI], theme="names of Allah"))["status"] == "not_quranic"


def test_ornate_script_is_never_trusted_even_with_a_perfect_score():
    # on Thuluth the model can write a fluent real verse from memory: the score cannot catch it
    d = reading.decide(analysis([KURSI], styles=("Thuluth",)))
    assert d["status"] == "unsure" and d["reason"] == "ornate_style"


def test_lines_pointing_to_different_places_are_not_trusted():
    d = reading.decide(analysis([KURSI, "قل هو الله احد الله الصمد لم يلد ولم يولد"]))
    assert d["status"] == "unsure" and d["reason"] == "lines_disagree"


def test_basmala_alone_and_short_readings_are_not_trusted():
    assert reading.decide(analysis(["بسم الله الرحمن الرحيم"]))["status"] == "unsure"
    assert reading.decide(analysis(["الحمد"]))["status"] == "unsure"
