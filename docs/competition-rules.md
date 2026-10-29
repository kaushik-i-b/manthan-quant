# Competition rules — verified versus unknown

The files `Hackathon_Problem_Statement.pdf` and `Beginners_Guide_to_Trading_and_Investment.pdf` were not in the repository. Nothing below the "Verified from the build brief" list is treated as an official schema.

## Verified from the build brief

| Item | Value |
| --- | --- |
| Portal | `http://192.168.65.157:3003` |
| API base | `http://192.168.65.157:3002/api/v1` |
| Kafka | `192.168.65.157:9094` |
| Topics | `market.ticks`, `market.news` |
| Starting capital | INR 1,000,000 |
| Cadence | about 3–4 real seconds per simulated day |
| News lag | about 150 ms after ticks |
| Documented routes | Portal page: `POST /orders`, `GET /orders`, `GET /portfolio`, `GET /portfolio/cash`, `GET /stocks`, `GET /stocks/history`, `GET /simulation/clock`, `GET /stage`, `POST /bot/heartbeat` |
| Actions named | `BUY`, `SELL`, `SHORT`, `COVER` |
| Rate limit | 120 requests / minute |
| Heartbeat | at least every 15 seconds |
| Fills | current-candle close |
| Auth | bearer token from `BOT_ACCESS_TOKEN` |
| Shorts | collateral and a mandatory square-off exist; numbers were not specified |

Portfolio, order-history, and other routes were named as "verify before use". They are not called.

## Unknown — fail closed

- Heartbeat JSON body
- Order JSON body and the response fields that mean "filled"
- Stage JSON and which value means trading is allowed
- Kafka message schema and the required consumer-group name
- Numeric brokerage, DP charges, and taxes
- Numeric short collateral and the square-off day count
- Idempotency key supported by the venue

Until a template file is configured, the engine will not POST a heartbeat or an order to the venue. A timeout on an order POST is marked `UNKNOWN`, the ticker is frozen, and the request is not retried.

## Local defaults (not official)

- `COST_MODEL=synthetic_demo`: ₹15 flat brokerage, zero tax
- `SHORT_COLLATERAL_PCT=1.0`
- `SHORT_MAX_HOLD_DAYS=5`
- Risk defaults: 10% position, 20% cash reserve, 8% drawdown, 80% invested

These risk numbers are starting configuration, not an optimised policy.
