from nun.chat.verify import check, numbers_ok, sentences

DOCS = {
    "D2": "(97) Indeed, We sent it down during the Night of Decree.",
    "D3": "Surah Al-Qadr is surah number 97 of the Quran; it is a Meccan surah; this passage is in juz 30.",
}


def test_sentences_split_on_arabic_and_latin_marks():
    assert sentences("أولًا [D1]. ثانيًا؟ Third! ") == ["أولًا [D1].", "ثانيًا؟", "Third!"]


def test_numbers_must_come_from_cited_documents():
    assert numbers_ok("It is in juz 30 [D3].", DOCS["D3"], set())
    assert not numbers_ok("It is in juz 55 [D3].", DOCS["D3"], set())
    assert numbers_ok("هي في الجزء ٣٠ [D3].", DOCS["D3"], set())  # Arabic-Indic digits


def test_check_drops_unsupported_number_and_judged_claim():
    text = "The verse speaks of the Night of Decree [D2]. It is the 2nd surah [D3]. It was revealed in Medina [D3]."

    def judge(system, user, schema):
        return {"unsupported": [2]}

    out, events = check(text, DOCS, set(), judge)
    assert out == "The verse speaks of the Night of Decree [D2]."
    assert "number_unsupported:1" in events and "claim_unsupported:2" in events


def test_judge_failure_keeps_number_layer():
    def judge(system, user, schema):
        raise RuntimeError("down")

    out, events = check("Juz 55 [D3]. Meccan [D3].", DOCS, set(), judge)
    assert out == "Meccan [D3]." and "judge_unavailable" in events
