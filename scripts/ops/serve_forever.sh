#!/usr/bin/env bash
# Nūn production supervisor (run by the Windows scheduled task "Nun", which keeps this WSL session open).
# Starts every service that is not running, then checks every 30 s and restarts only what died.
# The Cloudflare quick tunnel is started once and never restarted while it lives, so the public link stays the same;
# if it ever dies, it is restarted and the new link is written to data/public_url.txt (and logged).
cd "$(dirname "$0")/../.."
LOG=data/supervisor.log
mkdir -p data
say() { echo "$(date -Is) $*" >> "$LOG"; }
up() { curl -s -m 3 "$1" > /dev/null; }

start_ollama() {
  CUDA_VISIBLE_DEVICES=1 OLLAMA_KEEP_ALIVE=24h nohup bash scripts/ops/install_ollama_wsl.sh serve >> data/ollama.log 2>&1 &
  say "started ollama"
}
start_vision() {
  CUDA_VISIBLE_DEVICES=0 PYTHONPATH=. nohup ~/.venvs/nun/bin/uvicorn apps.vision.server:app --host 127.0.0.1 --port 8001 \
    >> data/vision.log 2>&1 &
  say "started vision"
}
start_api() {
  CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. nohup ~/.venvs/nun/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 \
    --workers 1 >> data/api.log 2>&1 &
  say "started api"
}
start_tunnel() {
  : > data/tunnel.log
  nohup ~/.local/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8000 >> data/tunnel.log 2>&1 &
  echo $! > data/tunnel.pid
  for _ in $(seq 1 60); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' data/tunnel.log | head -1)
    [ -n "$URL" ] && break
    sleep 1
  done
  echo "$URL" > data/public_url.txt
  say "started tunnel $URL"
}
tunnel_alive() { [ -f data/tunnel.pid ] && kill -0 "$(cat data/tunnel.pid)" 2> /dev/null; }

say "supervisor up"
while true; do
  up http://127.0.0.1:11435/api/tags || start_ollama
  up http://127.0.0.1:8001/health || { pgrep -f "uvicorn apps.vision.server" > /dev/null || start_vision; }
  up http://127.0.0.1:8000/api/health || { pgrep -f "uvicorn apps.api.main" > /dev/null || start_api; }
  tunnel_alive || start_tunnel
  sleep 30
done
