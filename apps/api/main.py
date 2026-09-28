"""Nūn API (M4 skeleton). Endpoints /api/scan, /api/verse, /api/chat arrive in M5–M6.

Run: make dev-api  (uvicorn apps.api.main:app)
"""

from __future__ import annotations

import json
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nun.config import settings

STARTED = time.time()

app = FastAPI(title="Nūn API", version="0.0.1", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings().web_origin],  # web origin only (SPEC §7)
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def corpus_status() -> dict:
    manifest = settings().corpus_dir / "MANIFEST.json"
    if not manifest.exists():
        return {"ready": False}
    m = json.loads(manifest.read_text(encoding="utf-8"))
    out = m["outputs"]["quran.jsonl"]
    return {
        "ready": (settings().corpus_dir / "quran.jsonl").exists(),
        "records": out["records"],
        "sha256": out["sha256"][:12],
    }


def gpu_status() -> list[dict]:
    try:
        import torch
    except ImportError:
        return []
    if not torch.cuda.is_available():
        return []
    out = []
    for i in range(torch.cuda.device_count()):
        free, total = torch.cuda.mem_get_info(i)
        out.append(
            {
                "index": i,
                "name": torch.cuda.get_device_name(i),
                "free_gib": round(free / 2**30, 1),
                "total_gib": round(total / 2**30, 1),
            }
        )
    return out


@app.get("/api/health")
def health() -> dict:
    corpus = corpus_status()
    return {
        "status": "ok" if corpus["ready"] else "degraded",
        "uptime_s": round(time.time() - STARTED),
        "corpus": corpus,
        "models": {"vlm": None, "embedder": None, "reranker": None},  # loaded in M5
        "gpus": gpu_status(),
    }
