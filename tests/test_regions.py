from nun.vlm.regions import align, parse, regions_for_card, verse_words

AYAH = {"aya": 114, "text_display": "فَتَعَٰلَى ٱللَّهُ ٱلْمَلِكُ ٱلْحَقُّ ۗ وَقُل رَّبِّ زِدْنِى عِلْمًا"}


def test_parse_full_and_truncated():
    raw = (
        '{"styles": ["Thuluth", "Foo"], "theme": "quranic", "regions": ['
        '{"bbox_1000_xywh": [77, 345, 856, 274], "text": "وَقُل رَّبِّ زِدْنِي عِلْمًا"},'
        '{"bbox_1000_xywh": [10, 10, 500, 2'  # cut off by the token cap
    )
    p = parse(raw)
    assert p["styles"] == ["Thuluth"]
    assert len(p["regions"]) == 1
    assert p["regions"][0]["box"] == [0.077, 0.345, 0.933, 0.619]


def test_parse_clamps_and_dedupes():
    raw = '[{"bbox_1000_xywh": [900, 0, 400, 100], "text": "ا"}, {"bbox_1000_xywh": [900, 0, 400, 100], "text": "ب"}]'
    p = parse(raw)
    assert len(p["regions"]) == 1
    assert p["regions"][0]["box"][2] == 1.0


def test_align_finds_span_and_skips_pause_marks():
    words = verse_words([AYAH])
    assert all(w[2] for w in words)  # the ۗ token is skipped
    span = align("وقل رب زدني علما", words)
    assert span == [[114, 5], [114, 6], [114, 7], [114, 8]]


def test_align_rejects_unrelated_reading():
    assert align("محمد رسول الله", verse_words([AYAH])) == []


def test_regions_for_card_drops_reading():
    parsed = {"styles": [], "regions": [{"box": [0, 0, 1, 1], "text": "وقل رب زدني علما"}]}
    out = regions_for_card(parsed, [AYAH])
    assert out == [{"box": [0, 0, 1, 1], "words": [[114, 5], [114, 6], [114, 7], [114, 8]]}]
    assert "text" not in out[0]
