# MANTHAN QUANT

Autonomous simulation desk for the MANTHAN 2026 trading challenge. The engine ingests a synthetic daily tape, updates indicators, selects a strategy, checks risk, fills on a local mock exchange, and streams the book to a dark trading terminal.

The official problem-statement PDFs were not in this repository. Venue order and heartbeat bodies are not guessed. Live submission stays off unless `DRY_RUN=false`, `TRADING_ENABLED=true`, `CONFIRM_LIVE_TRADING=I_UNDERSTAND`, a bearer token, and an official payload template are all set.

## What is real here

- Mock mode is the default. Prices, news, and P&L are synthetic and labeled as such.
- Fills use the current candle close, which is the execution rule stated in the build brief.
- Brokerage in the demo is a flat fictional ₹15 per fill (`COST_MODEL=synthetic_demo`). It is not the competition fee schedule.
- Short collateral (100%) and a 5-day square-off are local safety defaults, marked unverified.

## Run the desk

```bash
make install
make demo
```

- Desk: http://127.0.0.1:8742
- Engine: http://127.0.0.1:8741/api/health

Or two terminals:

```bash
make backend
make frontend
```

`make test` runs the Python suite and the frontend unit tests.

The first live simulated day is day 71. A RELIANCE buy typically prints within a few bars of the trend/news turn, and a deliberately oversized probe is rejected on day 78. Use **Simulate feed outage** on the Risk page to pause the tape and watch it recover. Pause and resume are local control commands; the browser never holds the venue token.

## Tests

```bash
cd backend && .venv/bin/pytest -q
cd frontend && npm test
```

## Venue connectivity

```bash
make probe
```

From this environment the private address `192.168.65.157` is not reachable. Do not enable live orders until the official PDFs confirm:

- heartbeat JSON
- order JSON
- stage response field that means "trading"
- fill status field
- Kafka consumer-group name
- brokerage, taxes, and the short square-off schedule

Template files are documented in `docs/api-contracts.md`.

## Layout

- `backend/` FastAPI engine, indicators, strategies, risk, mock exchange, backtests
- `frontend/` Next.js desk
- `docs/` contracts, rules, runbook, jury script

This is not investment advice. It is a hackathon simulation.
