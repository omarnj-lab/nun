"""Label tool: label → review → rejection loop, with a throwaway candidate list and log."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from label_tool import app as lt  # noqa: E402

pytestmark = pytest.mark.skipif(not Path("data/corpus/quran.jsonl").exists(), reason="run `make corpus` first")


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    (tmp_path / "images").mkdir()
    Image.new("RGB", (8, 8)).save(tmp_path / "images" / "a.jpg")
    cands = tmp_path / "candidates.jsonl"  # tmp_path acts as the "commons" source dir
    rows = [
        {"title": f"File:{n}.jpg", "file": "images/a.jpg", "sha1_original": n * 12, "source_url": "u", "license": "CC0"}
        for n in ("a", "b")
    ]
    cands.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    monkeypatch.setattr(lt, "SOURCES", {"commons": tmp_path, "duwat": tmp_path / "none"})
    monkeypatch.setattr(lt, "LOG", tmp_path / "log.jsonl")
    return TestClient(lt.app)


def test_locate_finds_verse_and_uthmani(client: TestClient) -> None:
    r = client.post("/api/locate", json={"text": "وقل رب زدني علما"}).json()
    assert [q["ref"] for q in r["quran"]] == ["20:114"]
    # the displayed text is the corpus record verbatim (never hand-typed Quran text in tests)
    assert r["quran"][0]["uthmani"] == lt.store().get(20, 114).text_uthmani


def test_ambiguous_fragment_lists_every_ref(client: TestClient) -> None:
    r = client.post("/api/locate", json={"text": "فبأي آلاء ربكما تكذبان"}).json()
    assert r["quran_total"] == 31


def test_label_review_reject_cycle(client: TestClient) -> None:
    first = client.get("/api/item").json()["id"]
    lab = {"id": first, "labeller": "A", "gt_type": "quran", "refs": [{"sura": 20, "aya_from": 114, "aya_to": 114}]}
    assert client.post("/api/label", json=lab).status_code == 200
    assert client.get("/api/item").json()["id"] != first  # moved on
    # the labeller cannot review their own label
    assert client.get("/api/item?mode=review&who=A").json()["id"] is None
    rv = {"id": first, "reviewer": "A", "verdict": "confirm"}
    assert client.post("/api/review", json=rv).status_code == 422
    # a second person rejects → the image returns to the label queue with the note
    assert (
        client.post("/api/review", json={**rv, "reviewer": "B", "verdict": "reject", "notes": "wrong ayah"}).status_code
        == 200
    )
    back = client.get("/api/item").json()
    assert back["id"] == first and back["review"]["notes"] == "wrong ayah"


def test_rejects_bad_refs(client: TestClient) -> None:
    bad = {"id": "rt-x", "labeller": "A", "gt_type": "quran", "refs": [{"sura": 1, "aya_from": 8, "aya_to": 8}]}
    assert client.post("/api/label", json=bad).status_code == 422
    assert client.post("/api/label", json={**bad, "refs": []}).status_code == 422


def test_image_path_traversal_blocked(client: TestClient) -> None:
    assert client.get("/img/commons/../candidates.jsonl").status_code == 404
    assert client.get("/img/nosuchsource/images/a.jpg").status_code == 404
    assert client.get("/img/commons/images/a.jpg").status_code == 200
