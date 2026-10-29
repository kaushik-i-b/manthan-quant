#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend" && (python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &) 
cd "$ROOT/frontend" && (npm run dev &)
sleep 6
curl -s http://127.0.0.1:8000/api/demo/reset || true
echo "MANTHAN QUANT demo up: frontend http://127.0.0.1:43123  backend http://127.0.0.1:8000"
