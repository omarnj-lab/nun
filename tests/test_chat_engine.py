"""Chat rules with a fake model: referral for personal rulings, citations required, no model-written Quran text,
no unsourced hadith. These test Nūn's guards, not a model."""

from pathlib import Path

import pytest

from nun.chat import engine

pytestmark = pytest.mark.skipif(not Path("data/corpus/quran.jsonl").exists(), reason="run `make corpus` first")


class FakeLLM:
    name, model = "fake", "fake-1"

    def __init__(self, route: dict, answers: list[str]) -> None:
        self.route, self.answers, self.calls, self.systems = route, list(answers), 0, []

    def complete_json(self, system, messages, schema):
        return dict(self.route)

    def complete(self, system, messages):
        self.calls += 1
        self.systems.append(system)
        return self.answers.pop(0) if self.answers else ""


def ask(monkeypatch, route, answers, question="What does it mean?", lang="en"):
    fake = FakeLLM(route, answers)
    monkeypatch.setattr(engine, "provider", lambda name=None: fake)
    return engine.answer(20, 114, 114, question, [], lang), fake


def test_cited_answer_passes(monkeypatch) -> None:
    out, _ = ask(monkeypatch, {"level": "A", "in_scope": True, "language": "en"}, ["It asks for knowledge [D2]."])
    assert out["answer"] == "It asks for knowledge [D2]." and [c["id"] for c in out["citations"]] == ["D2"]
    assert out["banner"].startswith("I am an AI assistant")


def test_uncited_answer_retried_then_safe_fallback(monkeypatch) -> None:
    out, fake = ask(monkeypatch, {"level": "B", "in_scope": True, "language": "en"}, ["No sources.", "Still none."])
    assert fake.calls == 2 and out["answer"] == engine.NOT_FOUND["en"] and out["citations"] == []


def test_personal_ruling_always_gets_referral(monkeypatch) -> None:
    # the model wrongly calls it out of scope; the fatwa cue must still route it to level D with a referral
    out, _ = ask(
        monkeypatch,
        {"level": "A", "in_scope": False, "language": "en"},
        ["General information only [D2]."],
        question="Is it halal for me to take this loan?",
    )
    assert out["level"] == "D" and out["referral"]


def test_model_written_quran_text_is_replaced(monkeypatch) -> None:
    out, _ = ask(
        monkeypatch, {"level": "A", "in_scope": True, "language": "en"}, ["The verse says وقل رب زدني علما [D1]."]
    )
    assert "زدني" not in out["answer"] and "see the verse on the card" in out["answer"]


def test_hadith_claims_removed(monkeypatch) -> None:
    out, _ = ask(
        monkeypatch,
        {"level": "B", "in_scope": True, "language": "en"},
        ["Knowledge matters [D2]. The Prophet said seeking knowledge is an obligation."],
    )
    assert "Prophet said" not in out["answer"] and "hadith_removed" in out["guard_events"]


def test_out_of_scope(monkeypatch) -> None:
    out, _ = ask(monkeypatch, {"level": "A", "in_scope": False, "language": "en"}, [], question="Best pizza in Riyadh?")
    assert out["answer"] == engine.OUT_OF_SCOPE["en"]


def test_auto_language_answers_in_visitor_language(monkeypatch):
    out, fake = ask(
        monkeypatch,
        {"level": "A", "in_scope": True, "language": "fr"},
        ["Il demande plus de savoir [D2]."],
        question="Que signifie ce verset ?",
        lang="auto",
    )
    assert out["language"] == "fr" and out["language_name"] == "Français"
    assert out["banner"].startswith("Je suis")
    assert "French" in fake.systems[-1] and "not as an official" in fake.systems[-1]


def test_picked_language_wins_and_unknown_messages_fall_back_to_english(monkeypatch):
    out, _ = ask(
        monkeypatch,
        {"level": "B", "in_scope": True, "language": "en"},
        ["none", "none"],
        question="What does it mean?",
        lang="sw",
    )
    assert out["language"] == "sw" and out["answer"] == engine.NOT_FOUND["en"]


def test_router_language_is_sanitised():
    from nun.chat import languages

    assert languages.clean("FR-ca", "x") == "fr"
    assert languages.clean("French!!", "ما معنى") == "ar"
    assert languages.guess("这是什么意思") == "zh"
    assert languages.clean("ar", "اس آیت کا کیا مطلب ہے؟") == "ur"
    assert languages.clean("ar", "این آیه چه معنایی دارد؟") == "fa"
    assert languages.clean("ar", "ما معنى هذه الآية؟") == "ar"
