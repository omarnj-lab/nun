# Run the production KhattVision call (structured: styles, theme, regions) over the internal set via the local
# vision service (127.0.0.1:8001). Output: data/private/fic/structured.jsonl (resumable). Internal images only.
import io
import json
from pathlib import Path

import csv
import httpx
from PIL import Image

FIC = Path("data/private/fic")
out = FIC / "structured.jsonl"
done = {json.loads(x)["file"] for x in out.read_text(encoding="utf-8").splitlines()} if out.exists() else set()
Image.MAX_IMAGE_PIXELS = None
rows = list(csv.DictReader(open(FIC / "labels.csv", encoding="utf-8")))
with out.open("a", encoding="utf-8") as f:
    for r in rows:
        if r["file"] in done:
            continue
        im = Image.open(FIC / r["file"])
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, "white")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        im = im.convert("RGB")
        im.thumbnail((1280, 1280))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        try:
            res = httpx.post("http://127.0.0.1:8001/analyze", content=buf.getvalue(), timeout=180).json()
        except Exception as e:  # noqa: BLE001
            res = {"error": str(e)[:200]}
        f.write(json.dumps({"file": r["file"], **res}, ensure_ascii=False) + "\n")
        f.flush()
        print(r["file"], res.get("styles"), res.get("theme"), res.get("seconds"), flush=True)
