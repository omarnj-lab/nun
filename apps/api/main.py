"""Nūn API + web app (Day 1 flow: photo → panel match → verse card → chat).

    PYTHONPATH=. uvicorn apps.api.main:app --host 127.0.0.1 --port 8000

/api/scan    photo → matcher against the product collection → the panel's verse card, or "couldn't identify".
             A verse is NEVER shown without a match. Photos are processed in memory and not stored.
/api/verse   verse card from the corpus (never generated).
/api/regions text regions of a matched photo from KhaṭṭVision (apps/vision, GPU 0), aligned to the verse words.
/api/chat    chat about one verse, from the verse documents with citations (provider: local | anthropic).
/admin       add-panel tool (HTTP Basic: ADMIN_PASSWORD in .env).
/            the web app (apps/web/dist).
"""

from __future__ import annotations

import base64
import io
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from nun import collection
from nun.card import build as build_card
from nun.config import settings
from nun.corpus.store import CorpusStore

load_dotenv()
Image.MAX_IMAGE_PIXELS = 80_000_000
MAX_UPLOAD = 15 * 1024 * 1024
WEB_DIST = Path("apps/web/dist")
WEB_PUBLIC = Path("apps/web/public")
ADMIN_HTML = Path(__file__).parent / "admin.html"
STARTED = time.time()

app = FastAPI(title="Nūn API", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
def warm_up() -> None:
    # build the matcher (and the chat's corpus index) in the background so the first visitor does not wait
    def work() -> None:
        matcher()
        from nun.chat.engine import _index

        _index()

    threading.Thread(target=work, daemon=True).start()


store = CorpusStore()
_matcher = None
_matcher_lock = threading.Lock()


def matcher():
    """The matcher over the product collection, built on first use and rebuilt when the collection changes."""
    global _matcher
    with _matcher_lock:
        if _matcher is None:
            from nun.match.matcher import PanelMatcher

            m = PanelMatcher()
            items = []
            for p in collection.load():
                im = Image.open(collection.images_dir() / p["file"]).convert("RGB")
                items.append((p["id"], im, p["id"], tuple(p["text_box"]) if p["text_box"] else None))
            m.add_many(items)
            _matcher = m
        return _matcher


def rebuild_matcher() -> None:
    global _matcher
    with _matcher_lock:
        _matcher = None
    matcher()


# ---- rate limiting (per client IP, sliding window) ----
_hits: dict[tuple[str, str], deque] = defaultdict(deque)
LIMITS = {"scan": (20, 60), "chat": (12, 60), "regions": (12, 60), "quiz": (20, 60)}  # (requests, seconds)


def client_ip(request: Request) -> str:
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")


def rate_limit(request: Request, kind: str) -> None:
    n, window = LIMITS[kind]
    q = _hits[(client_ip(request), kind)]
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= n:
        raise HTTPException(429, "Too many requests, please wait a minute.")
    q.append(now)


# ---- admin auth ----
def require_admin(request: Request) -> None:
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        raise HTTPException(503, "Admin is disabled: set ADMIN_PASSWORD in .env")
    expected = "Basic " + base64.b64encode(f"admin:{password}".encode()).decode()
    if not secrets.compare_digest(request.headers.get("authorization", ""), expected):
        raise HTTPException(401, "Login required", headers={"WWW-Authenticate": 'Basic realm="Nun admin"'})


async def read_image(upload: UploadFile) -> Image.Image:
    data = await upload.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Photo too large (max 15 MB)")
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Not an image") from None
    return ImageOps.exif_transpose(im).convert("RGB")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "uptime_s": round(time.time() - STARTED),
        "collection_panels": len(collection.load()),
        "matcher_loaded": _matcher is not None,
        "chat_provider_default": os.environ.get("CHAT_PROVIDER", "local"),
    }


@app.post("/api/scan")
async def scan(request: Request, image: UploadFile = File(...), lang: str = Form("ar")) -> dict:
    rate_limit(request, "scan")
    im = await read_image(image)
    t = time.perf_counter()
    m = matcher()
    res = m.match(im)
    elapsed = round((time.perf_counter() - t) * 1000)
    if not res.accepted:  # never guess
        return {"status": "uncertain", "timings_ms": {"match": elapsed}}
    panel = next(p for p in collection.load() if p["id"] == res.id)
    card = build_card(store, panel["sura"], panel["aya_from"], panel["aya_to"], "en" if lang != "ar" else "ar")
    return {
        "status": "matched",
        "panel": {
            "id": panel["id"],
            "inliers": res.inliers,
            "coverage": round(res.coverage, 2),
            "polygon": res.polygon,  # the panel boundary in the visitor's photo (fractions)
            "pairs": res.pairs,  # verified point pairs, photo ↔ reference (fractions), for "why we're sure"
            "reference": f"/panels/{panel['id']}.jpg"
            if (WEB_PUBLIC / "panels" / f"{panel['id']}.jpg").exists()
            else None,
        },
        "card": card,
        "timings_ms": {"match": elapsed},
    }


VISION_URL = os.environ.get("VISION_URL", "http://127.0.0.1:8001")


@app.post("/api/regions")
async def regions(
    request: Request,
    image: UploadFile = File(...),
    sura: int = Form(...),
    aya_from: int = Form(...),
    aya_to: int | None = Form(None),
) -> dict:
    """Where the text is in the visitor's photo and which verse words each region holds. Optional enrichment:
    the verse card never depends on it, and the model's reading never leaves the server."""
    import httpx

    from nun.vlm.regions import regions_for_card

    rate_limit(request, "regions")
    im = await read_image(image)
    try:
        card = build_card(store, sura, aya_from, aya_to or aya_from, "en")
    except KeyError:
        raise HTTPException(404, "No such verse") from None
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(f"{VISION_URL}/analyze", content=buf.getvalue())
        r.raise_for_status()
    except httpx.HTTPError:
        return {"available": False}
    out = r.json()
    return {
        "available": True,
        "styles": out.get("styles", []),
        "regions": regions_for_card(out, card["ayahs"]),
        "seconds": out.get("seconds"),
    }


@app.get("/api/journey/{sura}/{aya_from}/{aya_to}")
def journey_view(sura: int, aya_from: int, aya_to: int, lang: str = "en", panel: str | None = None) -> dict:
    from nun import journey

    try:
        return journey.journey(store, sura, aya_from, aya_to, "en" if lang != "ar" else "ar", panel)
    except KeyError:
        raise HTTPException(404, "No such verse") from None


@app.get("/api/quran-map")
def quran_map() -> JSONResponse:
    from nun import journey

    return JSONResponse(journey.quran_map(), headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/quiz/{sura}/{aya_from}/{aya_to}")
def quiz(sura: int, aya_from: int, aya_to: int) -> dict:
    from nun import journey

    try:
        return journey.quiz(store, sura, aya_from, aya_to)
    except KeyError:
        raise HTTPException(404, "No such verse") from None


class QuizResult(BaseModel):
    panel: str | None = Field(None, max_length=64)
    sura: int = Field(ge=1, le=114)
    aya: int = Field(ge=1, le=286)
    lang: str = Field("ar", max_length=5)
    pre_correct: bool | None = None
    post_correct: int = Field(ge=0, le=10)
    post_total: int = Field(ge=0, le=10)


@app.post("/api/quiz/result")
def quiz_result(request: Request, body: QuizResult) -> dict:
    """Anonymous understanding check (Track 03 success criterion): counts only, no identifiers."""
    from nun import journey

    rate_limit(request, "quiz")
    journey.record(body.panel, body.sura, body.aya, body.lang, body.pre_correct, body.post_correct, body.post_total)
    return {"ok": True}


@app.get("/api/quiz/stats")
def quiz_stats() -> dict:
    from nun import journey

    return journey.stats()


@app.get("/api/verse/{sura}/{aya}")
def verse(sura: int, aya: int, to: int | None = None, lang: str = "en") -> dict:
    try:
        return build_card(store, sura, aya, to, lang)
    except KeyError:
        raise HTTPException(404, "No such verse") from None


class ChatTurn(BaseModel):
    role: str
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    sura: int
    aya_from: int
    aya_to: int
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = []
    lang: str = Field("auto", max_length=8)  # "auto" = answer in the visitor's language, or an ISO 639-1 code
    provider: str | None = None


@app.post("/api/chat")
def chat(request: Request, body: ChatIn) -> dict:
    rate_limit(request, "chat")
    from nun.chat.engine import answer

    try:
        store.range(body.sura, body.aya_from, body.aya_to)
    except KeyError:
        raise HTTPException(404, "No such verse") from None
    try:
        return answer(
            body.sura,
            body.aya_from,
            body.aya_to,
            body.message,
            [t.model_dump() for t in body.history],
            body.lang,
            body.provider,
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    except Exception as e:  # noqa: BLE001 — model/provider unavailable
        raise HTTPException(503, f"The assistant is unavailable right now ({type(e).__name__}).") from None


# ---- admin: add-panel tool ----
@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request) -> str:
    require_admin(request)
    return ADMIN_HTML.read_text(encoding="utf-8")


@app.get("/api/admin/panels")
def admin_list(request: Request) -> dict:
    require_admin(request)
    return {"panels": collection.load()}


@app.get("/api/admin/panels/{panel_id}/image")
def admin_image(request: Request, panel_id: str) -> FileResponse:
    require_admin(request)
    p = next((p for p in collection.load() if p["id"] == panel_id), None)
    if not p:
        raise HTTPException(404)
    return FileResponse(collection.images_dir() / p["file"])


@app.post("/api/admin/panels")
async def admin_add(
    request: Request,
    image: UploadFile = File(...),
    panel_id: str = Form(...),
    sura: int = Form(...),
    aya_from: int = Form(...),
    aya_to: int = Form(...),
    box: str = Form(""),
) -> dict:
    require_admin(request)
    im = await read_image(image)
    text_box = [float(v) for v in box.split(",")] if box.strip() else None
    try:
        rec = collection.add(store, panel_id.strip().lower(), im, sura, aya_from, aya_to, text_box)
    except KeyError:
        raise HTTPException(422, "That verse does not exist") from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    rebuild_matcher()
    return {"ok": True, "panel": rec}


@app.delete("/api/admin/panels/{panel_id}")
def admin_delete(request: Request, panel_id: str) -> dict:
    require_admin(request)
    if not collection.remove(panel_id):
        raise HTTPException(404)
    rebuild_matcher()
    return {"ok": True}


# ---- the web app (single origin: no CORS needed) ----
@app.get("/{path:path}", include_in_schema=False)
def web(path: str) -> Response:
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    f = (WEB_DIST / path).resolve()
    if path and WEB_DIST.resolve() in f.parents and f.is_file():
        # hashed build files never change; images and icons rarely do. Cacheable responses are also kept at the
        # Cloudflare edge, which removes the tunnel round trip for repeat visitors.
        if path.startswith("assets/"):
            cache = "public, max-age=31536000, immutable"
        elif f.suffix in (".jpg", ".png", ".svg", ".webp", ".ico", ".webmanifest"):
            cache = "public, max-age=86400"
        else:
            cache = "no-cache"
        return FileResponse(f, headers={"Cache-Control": cache})
    index = WEB_DIST / "index.html"
    if not index.exists():
        return HTMLResponse("Web app not built: run npm run build in apps/web", status_code=503)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


_ = settings  # settings (referral contacts, origins) are read by the chat engine
