"""KhaṭṭVision service (internal only, 127.0.0.1): the team's v1 model on its own GPU, kept apart from the API so
restarting the API does not reload a 30B model.

    CUDA_VISIBLE_DEVICES=0 PYTHONPATH=. uvicorn apps.vision.server:app --host 127.0.0.1 --port 8001

POST /analyze (raw image bytes) → {styles, regions[{box, text}], seconds}. The reading in `text` is for aligning
regions to the verified verse inside the API; the API drops it before anything reaches a visitor.
"""

from __future__ import annotations

import io
import threading
import time

from fastapi import FastAPI, HTTPException, Request
from PIL import Image, ImageOps, UnidentifiedImageError

from nun.vlm.khatt_v1 import PROMPT_STRUCTURED, KhattV1
from nun.vlm.regions import parse

MAX_NEW_TOKENS = 512  # same as the team's HF Space (structured analysis)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_model: KhattV1 | None = None
_lock = threading.Lock()


@app.on_event("startup")
def load() -> None:
    def work() -> None:
        global _model
        _model = KhattV1(device=0)

    threading.Thread(target=work, daemon=True).start()


@app.get("/health")
def health() -> dict:
    return {"ready": _model is not None}


@app.post("/analyze")
async def analyze(request: Request) -> dict:
    if _model is None:
        raise HTTPException(503, "loading")
    data = await request.body()
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Not an image") from None
    t = time.perf_counter()
    with _lock:
        raw, _ = _model.generate(im, PROMPT_STRUCTURED, MAX_NEW_TOKENS)
    return {**parse(raw), "seconds": round(time.perf_counter() - t, 2)}
