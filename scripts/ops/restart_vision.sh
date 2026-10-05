#!/usr/bin/env bash
# Restart the KhaṭṭVision service on GPU 0 (≈ 25 s to load); waits until it is ready.
cd "$(dirname "$0")/../.."
pkill -f "uvicorn apps.vision.server:app" || true
sleep 3
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=. nohup ~/.venvs/nun/bin/uvicorn apps.vision.server:app --host 127.0.0.1 --port 8001 \
  > data/vision.log 2>&1 &
for _ in $(seq 1 120); do curl -s -m 2 http://127.0.0.1:8001/health | grep -q true && break; sleep 2; done
curl -s http://127.0.0.1:8001/health; echo
