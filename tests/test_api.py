"""API without the GPU: health, verse card, input validation, admin auth, no cross-origin access."""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api import main

pytestmark = pytest.mark.skipif(not Path("data/corpus/quran.jsonl").exists(), reason="run `make corpus` first")


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main, "warm_up", lambda: None)
    main.app.router.on_startup.clear()  # no matcher/GPU warm-up in unit tests
    return TestClient(main.app)


def test_health(client) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and "collection_panels" in body


def test_verse_card_from_corpus(client) -> None:
    card = client.get("/api/verse/20/114").json()
    assert card["ref"]["label"] == "20:114" and card["sura_name"]["ar"] == "طه"
    assert card["ayahs"][0]["text_uthmani"] == main.store.get(20, 114).text_uthmani  # verbatim corpus text
    assert card["ayahs"][0]["audio"].endswith("020114.mp3") and card["translation"]["translator"]
    assert client.get("/api/verse/1/8").status_code == 404


def test_scan_rejects_non_images(client) -> None:
    r = client.post("/api/scan", files={"image": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 415


def test_chat_rejects_unknown_verse(client) -> None:
    assert client.post("/api/chat", json={"sura": 1, "aya_from": 8, "aya_to": 8, "message": "hi"}).status_code == 404


def test_admin_requires_password(client, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    assert client.get("/api/admin/panels").status_code == 401
    good = base64.b64encode(b"admin:s3cret").decode()
    assert client.get("/api/admin/panels", headers={"Authorization": f"Basic {good}"}).status_code == 200


def test_no_cross_origin_access(client) -> None:
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers  # single-origin app: no CORS at all
