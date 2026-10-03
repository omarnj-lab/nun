"""End-to-end smoke test of the API in-process: scan (known + unknown), verse card, chat (local, anthropic).

CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. python scripts/ops/api_smoke.py [--anthropic]
"""

import io
import json
import random
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, "scripts")
from match_test import augment  # noqa: E402

from apps.api.main import app  # noqa: E402
from nun import collection  # noqa: E402

c = TestClient(app)


def jpeg(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=85)
    return buf.getvalue()


panel = collection.load()[0]
photo = augment(Image.open(collection.images_dir() / panel["file"]), "medium", random.Random(7))
t = time.perf_counter()
r = c.post("/api/scan", files={"image": ("p.jpg", jpeg(photo), "image/jpeg")}, data={"lang": "en"}).json()
print(
    f"known panel {panel['id']} ({panel['sura']}:{panel['aya_from']}): {r['status']} "
    f"{r.get('card', {}).get('ref', {}).get('label')} {r.get('panel')} in {time.perf_counter() - t:.1f}s"
)
unknown = next(Path("data/real/commons/images").glob("*.jpg"))
r2 = c.post("/api/scan", files={"image": ("u.jpg", unknown.read_bytes(), "image/jpeg")}).json()
print("unknown photo:", r2["status"])
v = c.get("/api/verse/2/255").json()
print("verse card 2:255:", v["sura_name"], v["juz"], v["revelation"])
print("  translation:", v["translation"]["translator"], "· audio:", v["ayahs"][0]["audio"])

providers = ["local"] + (["anthropic"] if "--anthropic" in sys.argv else [])
for prov in providers:
    for q, lang in [("What does this verse ask for?", "en"), ("هل يجوز لي أن أقترض بالربا لشراء بيت؟", "ar")]:
        t = time.perf_counter()
        body = {"sura": 20, "aya_from": 114, "aya_to": 114, "message": q, "lang": lang, "provider": prov}
        a = c.post("/api/chat", json=body).json()
        print(f"\n[{prov}] {q}  ({time.perf_counter() - t:.1f}s)")
        print(json.dumps({k: a.get(k) for k in ("level", "answer", "referral", "guard_events")}, ensure_ascii=False))
        print("citations:", [x["id"] for x in a.get("citations", [])])
