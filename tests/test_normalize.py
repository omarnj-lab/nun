import pytest

from nun.normalize.arabic import normalize, normalize_ns, split_segments

CASES = [
    # SPEC §3.3 required cases (Uthmani input)
    ("ٱللَّهُ", "الله"),
    ("ٱلرَّحۡمَٰنِ", "الرحمن"),
    ("زِدۡنِي", "زدني"),
    ("عِلۡمٗا", "علما"),
    # harakat / shadda / sukun
    ("بِسْمِ اللَّهِ", "بسم الله"),
    ("مُحَمَّدٌ", "محمد"),
    ("رَسُولُ", "رسول"),
    # hamza forms folded
    ("أحد", "احد"),
    ("إله", "اله"),
    ("آمنوا", "امنوا"),
    ("مؤمن", "مومن"),
    ("سئل", "سيل"),
    ("سماء", "سما"),
    ("شيء", "شي"),
    # alef maqsura / ta marbuta
    ("موسى", "موسي"),
    ("الصلاة", "الصلاه"),
    ("رحمة", "رحمه"),
    # tatweel
    ("اللـــه", "الله"),
    ("محـمـد", "محمد"),
    # dagger alef removed (Uthmani rasm kept as written)
    ("ٱلصَّلَوٰةَ", "الصلوه"),
    ("هَٰذَا", "هذا"),
    # Quranic annotation marks and small high letters
    ("وَحۡيُهُۥۖ", "وحيه"),
    ("ٱلۡحَقُّۗ", "الحق"),
    ("إِلَيۡكَ", "اليك"),
    # Uthmani rasm without the dagger alef differs from simple spelling: why matching uses text_simple
    ("ذَٰلِكَ ٱلۡكِتَٰبُ لَا رَيۡبَۛ", "ذلك الكتب لا ريب"),
    # punctuation, digits, Latin, ayah-end ornaments
    ("الحمد لله، رب العالمين.", "الحمد لله رب العالمين"),
    ("قل هو الله أحد ﴿١﴾", "قل هو الله احد"),
    ("Allah الله 123", "الله"),
    ("«سبحان الله»", "سبحان الله"),
    # whitespace collapsed, newlines become spaces
    ("  لا   إله\nإلا  الله ", "لا اله الا الله"),
    # Persian/Urdu letter forms
    ("کریم", "كريم"),
    ("علی", "علي"),
    ("اللہ نور", "الله نور"),  # heh goal (U+06C1), seen in DuwatBench gold text
    ("رحمۃ", "رحمه"),
    ("اللھ", "الله"),
    # empty / non-Arabic
    ("", ""),
    ("hello", ""),
]


@pytest.mark.parametrize(("raw", "expected"), CASES)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_case_count() -> None:
    assert len(CASES) >= 30


def test_idempotent() -> None:
    for raw, _ in CASES:
        once = normalize(raw)
        assert normalize(once) == once


def test_normalize_ns_removes_spaces() -> None:
    assert normalize_ns("وَقُل رَّبِّ زِدۡنِي عِلۡمٗا") == "وقلربزدنيعلما"


def test_uthmani_and_simple_agree_on_simple_words() -> None:
    assert normalize("وَقُل رَّبِّ زِدۡنِي عِلۡمٗا") == normalize("وقل رب زدني علما")


def test_split_segments_on_unreadable_marker() -> None:
    assert split_segments("وقل رب [؟] علما\nسبحان الله") == ["وقل رب", "علما", "سبحان الله"]
    assert split_segments("[؟]") == []
