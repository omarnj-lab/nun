#!/usr/bin/env bash
# Start the labelling tool, hit its endpoints once with real data, stop it. Usage: bash scripts/label_tool/live_check.sh
set -euo pipefail
PY=~/.venvs/nun/bin/python
~/.venvs/nun/bin/uvicorn scripts.label_tool.app:app --host 127.0.0.1 --port 8765 >/tmp/label_tool.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null' EXIT
for _ in $(seq 1 60); do curl -sf localhost:8765/api/stats >/dev/null && break; sleep 1; done
echo "stats: $(curl -s localhost:8765/api/stats)"
echo "page:  HTTP $(curl -s -o /dev/null -w '%{http_code}' localhost:8765/)"
curl -s localhost:8765/api/item | $PY -c 'import sys,json; d=json.load(sys.stdin); c=d["candidate"]; print("item: ", d["id"], "|", c["license"], "|", c["title"][:60])'
FILE=$(curl -s localhost:8765/api/item | $PY -c 'import sys,json; print(json.load(sys.stdin)["candidate"]["file"])')
echo "image: HTTP $(curl -s -o /dev/null -w '%{http_code} %{content_type} %{size_download}B' "localhost:8765/img/$FILE")"
curl -s -X POST localhost:8765/api/locate -H 'Content-Type: application/json' \
  -d '{"text":"الله لا إله إلا هو الحي القيوم"}' |
  $PY -c 'import sys,json; d=json.load(sys.stdin); print("locate:", [q["ref"] for q in d["quran"]])'
