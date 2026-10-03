#!/usr/bin/env bash
# Nūn live: local Ollama (if not running) + API/web on 127.0.0.1:8000 + Cloudflare quick tunnel (no account).
# Prints the public https://….trycloudflare.com link and writes it to data/public_url.txt. Ctrl+C stops everything.
# The link changes on every start. /admin needs ADMIN_PASSWORD (.env); the rest of the app is public by design.
set -euo pipefail
cd "$(dirname "$0")/../.."
PORT=8000
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-1}"
PIDS=()
trap 'kill "${PIDS[@]}" 2>/dev/null' EXIT INT TERM

if ! curl -s -m 3 http://127.0.0.1:11435/api/tags >/dev/null; then
  OLLAMA_KEEP_ALIVE=24h bash scripts/ops/install_ollama_wsl.sh serve > data/ollama.log 2>&1 &
  PIDS+=($!)
  for _ in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:11435/api/tags >/dev/null && break; sleep 1; done
fi
if ss -ltn | grep -q ":$PORT "; then echo "Port $PORT is busy: stop the other server first."; exit 1; fi

PYTHONPATH=. ~/.venvs/nun/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port $PORT --workers 1 > data/api.log 2>&1 &
PIDS+=($!)
for _ in $(seq 1 120); do curl -s -m 2 http://127.0.0.1:$PORT/api/health >/dev/null && break; sleep 1; done

~/.local/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:$PORT > data/tunnel.log 2>&1 &
PIDS+=($!)
URL=""
for _ in $(seq 1 60); do URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' data/tunnel.log | head -1 || true); [ -n "$URL" ] && break; sleep 1; done
echo "${URL:-tunnel failed: see data/tunnel.log}" | tee data/public_url.txt
wait
