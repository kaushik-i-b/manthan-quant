# Architecture

```text
mock tape or Kafka
        │
        ▼
  per-ticker book ──► incremental indicators
        │
        ▼
  regime selector ──► proposal (BUY/SELL/SHORT/COVER/HOLD)
        │
        ▼
  risk gate ──► single-writer fill (mock close, or templated venue POST)
        │
        ▼
  portfolio ──► SQLite audit + WebSocket desk
```

The dashboard is a subscriber. Disconnecting it does not stop the engine. Indicator updates and risk checks run on the feed task; they do not perform venue HTTP. Venue calls go through a shared rate limiter (120/minute) and only when venue mode is armed.

Mock replay warms indicators through day 70 with orders disabled, acknowledges a local heartbeat, holds PREFLIGHT for about a second, then trades. News for a day is applied 150 ms after that day's candles, and the decision uses the candle close plus news that is already visible. Later days are not readable.

Backtests call the same proposal, risk, cost, and portfolio code. A threshold grid is scored on days 50–95. Validation (96–127) is reported and not used for selection. The test window is days 128–159.

SQLite (`backend/data/manthan.db`) stores non-hold decisions and orders. The live desk reads the in-memory tape.

Redis is not used. One process is enough for eight names and a multi-second bar.

On this machine (Python 3.12, in-process mock, seed 42), the decision loop over the last 400 evaluations of a 160-day instant replay measured p50 0.020 ms and max 0.37 ms. That is local CPU time only. It is not a venue-network or Kafka benchmark. `pytest` asserts the same loop stays under 100 ms so a regression is caught without treating the millisecond figure as a guarantee.
