"""Smoke test of the WSL Ollama server: list models, then one short Arabic/English chat with timing."""

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:11435"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:latest"

with urllib.request.urlopen(BASE + "/api/tags", timeout=30) as r:
    print("models:", [m["name"] for m in json.load(r)["models"]])
body = {
    "model": MODEL,
    "stream": False,
    "think": False,
    "messages": [{"role": "user", "content": "In one sentence: what does the Arabic word «علما» mean?"}],
}
t = time.perf_counter()
headers = {"Content-Type": "application/json"}
req = urllib.request.Request(BASE + "/api/chat", data=json.dumps(body).encode(), headers=headers)
with urllib.request.urlopen(req, timeout=900) as r:
    out = json.load(r)
print(f"{MODEL}: {time.perf_counter() - t:.1f}s →", out["message"]["content"][:300])
print("eval tokens/s:", round(out.get("eval_count", 0) / max(out.get("eval_duration", 1) / 1e9, 1e-9), 1))
