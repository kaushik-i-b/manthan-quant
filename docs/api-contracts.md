# API contracts

Portal extraction on 29 October 2026 did not reach `http://192.168.65.157:3003` from this machine (HTTP timed out after 5 seconds; TCP connect to ports 3003, 3002, and 9094 failed). `MANTHAN_PORTAL_PASSWORD` was not set. No request or response schema below is portal-verified. See `docs/api-discovery-report.md`.

Paths named in the build brief stay fail-closed until `scripts/extract_portal_contracts.py` saves an OpenAPI document on the venue network. The dry-run simulator does not call them.

## Venue routes that exist in the build brief

The client can call only:

- `GET /api/v1/stocks`
- `GET /api/v1/stocks/{ticker}/history`
- `GET /api/v1/stage`
- `POST /api/v1/bot/heartbeat`
- `POST /api/v1/orders`

GET requests may retry on timeout, network errors, HTTP 429, and HTTP 5xx (two retries, exponential backoff). `POST /orders` is never retried.

Authorization is `Bearer $BOT_ACCESS_TOKEN`. The token is redacted in logs and is not sent to the browser.

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
