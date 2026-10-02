"""Panel review app: choices are saved to review.csv, panels can be grouped, the Quran search works."""

import csv
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import review_app as ra  # noqa: E402

FIELDS = ["file", "license", "author", "url", "reading"] + [f"suggestion_{i}" for i in range(1, 6)]
FIELDS += ["confirmed_ref", "type", "panel_group", "notes"]


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    (tmp_path / "raw").mkdir()
    rows = []
    for i in range(3):
        Image.new("RGB", (8, 8)).save(tmp_path / "raw" / f"p{i}.jpg")
        rows.append({k: "" for k in FIELDS} | {"file": f"p{i}.jpg", "license": "CC0", "reading": "x"})
    rows[0]["suggestion_1"] = "20:114 — " + ra.vid.ref_text("20:114")
    with (tmp_path / "review.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    monkeypatch.setattr(ra, "PANELS", tmp_path)
    monkeypatch.setattr(ra, "REVIEW", tmp_path / "review.csv")
    return TestClient(ra.app)


def saved(client) -> list[dict]:
    return list(csv.DictReader(ra.REVIEW.open(encoding="utf-8")))


def test_choose_suggestion_is_saved(client) -> None:
    p = client.get("/api/panel/1").json()
    assert p["suggestions"][0]["ref"] == "20:114"
    assert client.post("/api/panel/1", json={"type": "quran", "confirmed_ref": "20:114"}).status_code == 200
    r = saved(client)[0]
    assert (r["type"], r["confirmed_ref"], r["panel_group"]) == ("quran", "20:114", "P001")


def test_invalid_reference_rejected(client) -> None:
    assert client.post("/api/panel/1", json={"type": "quran", "confirmed_ref": "1:8"}).status_code == 422
    assert client.post("/api/panel/1", json={"type": "poem"}).status_code == 422


def test_same_panel_groups_both(client) -> None:
    client.post("/api/panel/3", json={"type": "other", "same_as": 2})
    rows = saved(client)
    assert rows[2]["panel_group"] == rows[1]["panel_group"] == "P002"
    assert rows[2]["type"] == "other" and rows[2]["confirmed_ref"] == ""


def test_search_by_ref_and_words(client) -> None:
    assert client.get("/api/search", params={"q": "2:255"}).json()["results"][0]["ref"] == "2:255"
    refs = [x["ref"] for x in client.get("/api/search", params={"q": "زدني علما"}).json()["results"]]
    assert "20:114" in refs


def test_image_traversal_blocked(client) -> None:
    assert client.get("/img/..%2Freview.csv").status_code == 404
