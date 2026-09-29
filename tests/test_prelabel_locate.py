"""Line-by-line location of a (simulated) model reading; references come from the corpus."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

pytestmark = pytest.mark.skipif(not Path("data/corpus/quran.jsonl").exists(), reason="run `make corpus` first")


def locate(text: str) -> list[dict]:
    from prelabel_claude import locate_lines

    return locate_lines(text)[0]


def R(s: int, a: int, b: int) -> dict:
    return {"sura": s, "aya_from": a, "aya_to": b}


def test_basmala_header_over_a_verse_gives_the_verse() -> None:
    reading = "بسم الله الرحمن الرحيم\nكهيعص\nذكر رحمة ربك عبده زكريا"
    assert locate(reading) == [R(19, 1, 2)]


def test_basmala_alone_is_ambiguous() -> None:
    assert locate("بسم الله الرحمن الرحيم") == [R(1, 1, 1), R(27, 30, 30)]


def test_unreadable_gaps_split_segments() -> None:
    # Ayat al-Kursi opening with an unreadable middle part: both halves locate inside 2:255 (and 3:2 for the first)
    refs = locate("الله لا إله إلا هو الحي القيوم [؟] لا تأخذه سنة ولا نوم")
    assert R(2, 255, 255) in refs


def test_non_quran_text_is_not_located() -> None:
    assert locate("ديوان الحماسة\nأبو تمام") == []


def test_common_words_do_not_produce_references() -> None:
    assert locate("[؟] الله [؟]\nالحمد [؟]") == []


def test_layout_notes_are_ignored() -> None:
    reading = "الصفحة اليمنى، الكرتوش العلوي: بسم الله الرحمن الرحيم\n(ترجمة فارسية بين السطور)"
    assert locate(reading) == [R(1, 1, 1), R(27, 30, 30)]


def test_repeated_phrase_keeps_all_its_places() -> None:
    refs = locate("هو الذي أرسل رسوله بالهدى ودين الحق ليظهره على الدين كله")
    assert {(r["sura"], r["aya_from"]) for r in refs} == {(9, 33), (48, 28), (61, 9)}
