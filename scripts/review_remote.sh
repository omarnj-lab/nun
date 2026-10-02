#!/usr/bin/env bash
# Panel review app for remote reviewers: app on 127.0.0.1:8766 + Cloudflare quick tunnel (https://….trycloudflare.com).
# Requires REVIEW_PASSWORD in .env (refuses to expose the app without a login). Ctrl+C stops both.
# Quick tunnels need no Cloudflare account; the link changes on every start and has no uptime guarantee.
set -euo pipefail
cd "$(dirname "$0")/.."
grep -qE '^REVIEW_PASSWORD=.+' .env || { echo "Set REVIEW_PASSWORD in .env first"; exit 1; }
PORT=8766
if ss -ltn | grep -q ":$PORT "; then echo "Port $PORT is busy (another review app?). Stop it first."; exit 1; fi
LOG=data/panels/tunnel.log
PYTHONPATH=. ~/.venvs/nun/bin/uvicorn scripts.review_app:app --host 127.0.0.1 --port $PORT > data/panels/review_app.log 2>&1 &
APP=$!
trap 'kill $APP $TUN 2>/dev/null' EXIT INT TERM
for _ in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:$PORT/ && break; sleep 1; done
~/.local/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:$PORT > "$LOG" 2>&1 &
TUN=$!
for _ in $(seq 1 60); do URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1) && [ -n "$URL" ] && break; sleep 1; done
echo "Review app (login required): ${URL:-tunnel failed, see $LOG}"
echo "$URL" > data/panels/tunnel_url.txt
wait $TUN
