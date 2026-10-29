#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x backend/.venv/bin/uvicorn ]]; then
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -r backend/requirements.txt
fi
if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm install)
fi

mkdir -p backend/data
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8741 &
BACK_PID=$!
(cd frontend && npm run dev) &
FRONT_PID=$!
trap 'kill $BACK_PID $FRONT_PID 2>/dev/null || true' EXIT
echo "Engine  http://127.0.0.1:8741/api/health"
echo "Desk    http://127.0.0.1:8742"
wait
