from fastapi.testclient import TestClient

from apps.api.main import app


def test_health() -> None:
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert set(body["models"]) == {"vlm", "embedder", "reranker"}


def test_cors_only_web_origin() -> None:
    c = TestClient(app)
    ok = c.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    other = c.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
