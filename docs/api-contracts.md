# API contracts

The participant portal API reference page was read from an uploaded screenshot dated 10/29/26, 10:49 PM. Paths and the identifiers printed on that page are VERIFIED. JSON bodies were not shown, so they stay unresolved. The private network was not contacted. No order was submitted.

## VERIFIED paths

The client base URL is `http://192.168.65.157:3002/api/v1` from the build brief. The page prints these paths:

| Method | Path | What the page says | Schema |
| --- | --- | --- | --- |
| POST | `/api/v1/orders` | BUY, SELL, SHORT, COVER market order. Optional `date` is the decision market date and does not change the fill price. | unresolved |
| GET | `/api/v1/orders` | Audit log, fill prices, rejection reasons, timestamps. | unresolved |
| GET | `/api/v1/portfolio` | Cash, long and short holdings, mark-to-market, realized and unrealized P&L. Short `quantity` is negative, `is_short` is true, `market_value` is a negative liability (`quantity × current_price`). `unrealized_pnl` is named; the rest of that sentence was cut off. | unresolved |
| GET | `/api/v1/portfolio/cash` | Cash balance for position sizing. | unresolved |
| GET | `/api/v1/stocks` | Tradable universe during READY and PRE-FLIGHT: ticker, masked company name, short description. Do not hardcode tickers. | unresolved |
| GET | `/api/v1/stocks/history` | Daily OHLCV, up to 10 years, default strictly before the simulation date. Query `ticker`, `start_date`, `end_date`, or `days`. An early range errors with the listing date. | unresolved |
| GET | `/api/v1/simulation/clock` | Current day, total days, remaining days, interval speed, simulated date. | unresolved |
| GET | `/api/v1/stage` | Stage, active database, progress. Labels named: development, ready, preflight, simulation. Which label allows orders is unresolved. | unresolved |
| POST | `/api/v1/bot/heartbeat` | Acknowledge the pre-flight Kafka ping `seq`. | unresolved |

Historical bars are `GET /api/v1/stocks/history?ticker=`, not `/api/v1/stocks/{ticker}/history`.

## Still needed before a live bot

- JSON request body for `POST /orders` besides the optional `date` name
- JSON body for `POST /bot/heartbeat` besides the name `seq`
- Response JSON for every GET, including cash, clock, stocks, history, stage, and orders
- Which stage value permits orders
- Whether the bot sends `Cookie: access_token=...` or `Authorization: Bearer ...`
- Kafka topic payloads, consumer group, and the heartbeat `seq` message
- Brokerage, DP charges, tax, short collateral, and square-off

`DRY_RUN` stays true and `TRADING_ENABLED` stays false. The engine will not build those bodies.

## Client behavior

The client can call the nine paths in the table above. History is `GET /stocks/history` with the printed query names. GET requests may retry on timeout, network errors, HTTP 429, and HTTP 5xx (two retries, exponential backoff). `POST /orders` is never retried.

The portal console authenticates with a cookie named `access_token`. Whether the bot uses that cookie or `Authorization: Bearer` is unresolved. A configured `BOT_ACCESS_TOKEN` is still sent as a bearer header by the existing client and is redacted in logs. It is not sent to the browser. Order and heartbeat bodies are still refused unless an operator supplies a template file.

## Templates

If `VENUE_HEARTBEAT_TEMPLATE_PATH` or `VENUE_ORDER_TEMPLATE_PATH` is unset, the corresponding POST is refused.

A template is a JSON object. String values may contain `{ticker}`, `{action}`, `{quantity}`, `{price}`, `{sim_day}`, `{client_order_id}`, `{stage}`, `{ts}`. No extra keys are added.

A venue order is marked `FILLED` only when `VENUE_ORDER_STATUS_FIELD` is present and equals `VENUE_ORDER_STATUS_VALUE`. Otherwise a 200 response is `UNKNOWN` and the ticker is frozen. Local positions after a parsed venue fill are labeled `estimated`.

`GET /stage` updates the stage only when `VENUE_STAGE_STAGE_FIELD` is set. The stage becomes `TRADING` only when that field equals `VENUE_STAGE_ACTIVE_VALUE`.

## Internal schemas (mock and tests only)

These are not competition Kafka schemas.

Tick `manthan-quant.internal.tick.v1`:

```json
{
  "schema_name": "manthan-quant.internal.tick.v1",
  "event_id": "RELIANCE-75",
  "ticker": "RELIANCE",
  "sim_day": 75,
  "ts_unix": 1704067200,
  "open": 2450,
  "high": 2460,
  "low": 2445,
  "close": 2455,
  "volume": 2400000,
  "source": "synthetic"
}
```

News `manthan-quant.internal.news.v1` adds `headline` and `body`.

Unknown payloads are audited as `schema_rejected` and are not traded. Duplicates and out-of-order bars (`sim_day` less than or equal to the last accepted day) are dropped. A gap is counted and the later bar is still accepted.

Kafka consumption, when enabled, uses manual commit after the handler returns. A schema rejection is still committed so one poison message cannot stall the group. `KAFKA_GROUP_ID` must be set to the official name; the default is empty and the consumer will not start.

## Desk API (this application)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | process health |
| GET | `/api/snapshot` | full desk state |
| GET | `/api/candles/{ticker}` | enriched bars |
| GET | `/api/audit` | filterable audit |
| POST | `/api/control/pause` | bearer `CONTROL_TOKEN` |
| POST | `/api/control/resume` | bearer `CONTROL_TOKEN` |
| POST | `/api/demo/outage` | mock mode only |
| POST | `/api/venue/probe` | GET `/stage` only, no orders |
| POST | `/api/backtest/compare` | synthetic tape |
| WS | `/api/ws` | snapshot, then events |

WebSocket event names (`market.tick`, `market.news`, `strategy.signal`, `order.result`, `portfolio.updated`, `risk.alert`, `system.health`, `simulation.stage`) are internal. They are not claims about Kafka.
