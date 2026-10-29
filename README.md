# MANTHAN QUANT — Autonomous AI Trading Platform

Competition-ready algorithmic trading system with a premium real-time terminal for MANTHAN 2026.

## What this is

- **Backend** (`backend/`): FastAPI engine — mock/venue market ingestion (Kafka `market.ticks` + `market.news` with mock fallback), incremental indicator engine, 5 deterministic strategies + adaptive regime selector, independent risk engine, single-writer execution queue, portfolio accounting, backtesting, heartbeat/lifecycle manager, WebSocket fan-out.
- **Frontend** (`frontend/`): Next.js 14 dark institutional terminal — Overview, Market Terminal (TradingView Lightweight Charts), AI Strategy Center, Portfolio, Execution Monitor, Risk Center, Backtest Lab. Live updates over WebSocket with auto-reconnect + staleness detection.

## Quickstart (local, no venue network needed)

```bash
# 1. Backend
cd backend && pip install -r requirements.txt
python3 -m pytest tests/ -q
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. Frontend (new shell)
cd frontend && npm install && npm run dev
# open http://127.0.0.1:43123
```

Or one-command demo: `bash scripts/demo.sh` (starts both, resets the sim).

## Safety defaults

- `DRY_RUN=true`, `TRADING_ENABLED=false`, `MOCK_MODE=true` — the engine observes and explains but submits no venue orders until you explicitly flip these **with** a real `BOT_ACCESS_TOKEN`.
- Risk engine is independent: it vetoes signals on drawdown, cash reserve, concentration, rate, and stage gates.

## Venue connectivity (competition Wi-Fi only)

The venue IPs (`192.168.65.157:3002/3003`, Kafka `:9094`) are private-network addresses — reachable only on the competition network. To go live:

1. Copy `.env.example` → `.env`, set `BOT_ACCESS_TOKEN`, `MOCK_MODE=false`, `TRADING_ENABLED=true` (keep `DRY_RUN=true` until the jury approves).
2. Verify schemas against `docs/api-contracts.md`, then `GET /api/v1/stocks`, `GET /api/v1/stage`, `POST /api/v1/bot/heartbeat`.
3. Confirm Kafka topics flow, then enable.

Never commit real tokens. Frontend never sees secrets.

## Docs

- `docs/architecture.md` · `docs/api-contracts.md` · `docs/strategy-design.md`
- `docs/competition-rules.md` · `docs/runbook.md` · `docs/jury-demo.md` (5-min script)
