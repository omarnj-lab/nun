#!/usr/bin/env bash
# Rebuild the web app and restart only the API server; the Cloudflare tunnel (and its public link) stays up.
set -e
cd /mnt/c/Users/User/Desktop/Nun_handoff/handoff
pkill -f "uvicorn apps.api.main:app" || true
sleep 2
source ~/.nvm/nvm.sh >/dev/null
(cd apps/web && npm run typecheck 2>&1 | tail -5 && npx vite build 2>&1 | tail -1)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. nohup ~/.venvs/nun/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --workers 1 > data/api.log 2>&1 &
for i in $(seq 1 120); do curl -s -m 2 http://127.0.0.1:8000/api/health >/dev/null && break; sleep 1; done
curl -s http://127.0.0.1:8000/api/health; echo
curl -s -m 10 "$(cat data/public_url.txt)/api/health"; echo
