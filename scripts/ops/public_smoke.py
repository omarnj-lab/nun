"""Done-criteria check through the PUBLIC link: real phone photo → card; unknown photo → refused; two chat answers
with citations. Usage: python scripts/ops/public_smoke.py https://….trycloudflare.com [local|anthropic]"""

import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

BASE = sys.argv[1].rstrip("/")
PROVIDER = sys.argv[2] if len(sys.argv) > 2 else "local"


def post_image(path: Path) -> dict:
    boundary = uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="lang"\r\n\r\nen\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="p.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = urllib.request.Request(
        BASE + "/api/scan", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def chat(card: dict, q: str) -> dict:
    ref = card["ref"]
    body = {
        "sura": ref["sura"],
        "aya_from": ref["aya_from"],
        "aya_to": ref["aya_to"],
        "message": q,
        "lang": "en",
        "provider": PROVIDER,
    }
    req = urllib.request.Request(
        BASE + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


t = time.perf_counter()
r = post_image(Path("data/real_test/queries/real_ayat_alkursi__1.jpg"))
print(
    f"real phone photo (Ayat al-Kursi): {r['status']} {r.get('card', {}).get('ref', {}).get('label')} "
    f"{r.get('panel')} · {time.perf_counter() - t:.1f}s"
)
u = post_image(next(Path("data/real/commons/images").glob("*.jpg")))
print("photo not in the collection:", u["status"])
card = r["card"]
for q in ["What is this verse about?", "Which surah is it in, and is it Meccan or Medinan?"]:
    t = time.perf_counter()
    a = chat(card, q)
    print(f"\nQ: {q}  [{a['provider']} {a['model']}, {time.perf_counter() - t:.1f}s, level {a['level']}]")
    print("A:", a["answer"])
    print("citations:", [c["id"] for c in a["citations"]])
