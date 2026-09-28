import pytest

from eval.metrics import compute, coverage_curve, overlaps


def R(s: int, a: int, b: int | None = None) -> dict:
    return {"sura": s, "aya_from": a, "aya_to": b or a}


GTS = [
    {"id": "q1", "gt_type": "quran", "refs": [R(20, 114)], "gt_text": "وقل رب زدني علما"},
    {"id": "q2", "gt_type": "quran", "refs": [R(2, 255)], "gt_text": "الله لا إله إلا هو"},
    {"id": "q3", "gt_type": "quran", "refs": [R(112, 1, 4)], "gt_text": "قل هو الله أحد"},
    {"id": "n1", "gt_type": "name", "refs": [], "list_ids": ["n:01"], "gt_text": "الرحمن"},
    {"id": "o1", "gt_type": "other", "refs": [], "gt_text": "ديوان"},
    {"id": "o2", "gt_type": "other", "refs": [], "gt_text": ""},
]
PREDS = [
    # right, verified
    {"id": "q1", "status": "verified", "refs": [R(20, 114)], "confidence": 0.99, "reading": "وقل رب زدني علما"},
    # WRONG but verified → a confident error
    {"id": "q2", "status": "verified", "refs": [R(3, 2)], "candidates": [[R(3, 2)], [R(2, 255)]], "confidence": 0.95},
    # abstained, but the right ref was in the top 5 candidates
    {"id": "q3", "status": "uncertain", "refs": [], "candidates": [[R(112, 2)]], "confidence": 0.4},
    {"id": "n1", "status": "partial", "list_ids": ["n:01"], "confidence": 0.8},
    {"id": "o1", "status": "out_of_scope", "confidence": 0.1, "reading": "ديوان"},
    # answering on an "other" image → also a confident error
    {"id": "o2", "status": "verified", "refs": [R(1, 1)], "confidence": 0.9},
]


def test_overlap() -> None:
    assert overlaps(R(2, 255), R(2, 250, 256))
    assert not overlaps(R(2, 255), R(3, 255))
    assert not overlaps(R(2, 255), R(2, 256, 257))


def test_compute() -> None:
    m = compute(GTS, PREDS)
    assert m["n"] == 6
    assert m["verse_id_top1"] == pytest.approx(1 / 3, abs=1e-3)
    assert m["verse_id_top5"] == pytest.approx(3 / 3)  # q2 via candidate #2, q3 via candidate 112:2 ⊂ 112:1-4
    assert m["coverage"] == pytest.approx(3 / 4)  # q1, q2, n1 answered of 4 in scope
    assert m["selective_accuracy"] == pytest.approx(2 / 3, abs=1e-3)  # q1 ✓ q2 ✗ n1 ✓
    assert m["confident_errors"] == ["q2", "o2"]
    assert m["confident_error_rate"] == pytest.approx(2 / 6, abs=1e-3)
    assert m["abstention_correctness"] == pytest.approx(1 / 2)
    assert m["reading"]["n"] == 5 and m["reading"]["cer"] is not None


def test_missing_prediction_is_an_error() -> None:
    with pytest.raises(ValueError):
        compute(GTS, PREDS[:-1])


def test_coverage_curve_monotone_coverage() -> None:
    c = coverage_curve(GTS, PREDS)
    assert [p["coverage"] for p in c] == sorted(p["coverage"] for p in c)
    assert c[0]["accuracy"] == 1.0 and c[-1]["coverage"] == 1.0
