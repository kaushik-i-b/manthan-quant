# Runbook

## Start / stop
- Backend: `python3 -m uvicorn app.main:app --port 8000` (from `backend/`) · health: `GET /api/health`.
- Frontend: `npm run dev` (port 43123).
- Reset demo: `POST /api/demo/reset`.

## If Kafka drops
Engine falls back to deterministic mock stream; `system.health.kafka` shows mode. Reconnect uses exponential backoff; offsets are manual-commit so nothing is double-counted.

## If API 429s
Client backs off exponentially, counts against the 110/min budget shown in Execution Monitor. Orders stay queued (max 200) — nothing is blindly retried when fill status is unknown.

## Emergency
Risk Center → **Pause trading** (`POST /api/risk/pause`) halts new orders immediately; existing positions are untouched. Resume only after reviewing violations.

## Pre-flight checklist
1. `pytest` green · 2. `/api/health` stage TRADING · 3. heartbeat OK · 4. rate usage < 50% · 5. risk HEALTHY · 6. DRY_RUN confirmed on screen.
