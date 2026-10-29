# API Contracts (verify against live venue docs before trading)

Base: `http://192.168.65.157:3002/api/v1` · Limit: 120 req/min (client caps at 110).

| Endpoint | Method | Notes |
|---|---|---|
| `/stocks` | GET | Symbol discovery — do not hardcode list |
| `/stocks/:ticker/history` | GET | Warm-up only, respect anti-lookahead |
| `/stage` | GET | Simulation stage gate for orders |
| `/bot/heartbeat` | POST | Body `{"ack": true, "correlationId": "…"}` — at least every 15 s (we send every 10 s) |
| `/orders` | POST | `{"ticker","action":"BUY\|SELL\|SHORT\|COVER","quantity"}` — executed at current-candle close per sim rules |

Unverified (do not use until confirmed in official docs): portfolio / order-history endpoints — the engine reconciles from order responses + mock fills instead of assuming them.

Kafka: `market.ticks`, `market.news` on `192.168.65.157:9094`, consumer group `manthan-quant-bot-v1`, manual offset commits, `latest` reset. News may lag ticks ~150 ms — handled via `news_fresh` 2-day window.
