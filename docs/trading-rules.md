# Trading rules

The portal and both PDFs were unavailable during this extraction. Nothing in this file was copied from a logged-in rules page.

## INFERRED from the build brief

| Rule | Value |
| --- | --- |
| Starting capital | INR 1,000,000 |
| Actions named | BUY, SELL, SHORT, COVER |
| Fill price | current candle close |
| Cadence | about 3–4 real seconds per simulated day |
| News lag | about 150 ms after ticks |
| Rate limit | 120 requests per minute |
| Heartbeat | at least every 15 seconds |
| Shorts | collateral and a mandatory square-off exist |

## VERIFIED from the portal API reference screenshot

- Order actions named on the page: BUY, SELL, SHORT, COVER. They are market orders.
- SHORT credits cash and stores a negative quantity. COVER realizes `(Short Price - Cover Price) x Shares`.
- Optional order attribute `date` records the decision market date and does not change the execution price.
- History defaults to daily OHLCV strictly before the current simulation date.
- Stage labels named on the page: development, ready, preflight, simulation. Which one allows orders is unresolved.
- Heartbeat acknowledges a Kafka pre-flight ping called `seq`. The message schema is unresolved.
- The stock list is available during READY and PRE-FLIGHT, before the first tick.

## MISSING from the portal screenshot

- Collateral ratio
- Square-off schedule
- Brokerage
- DP charges
- Taxation
- Pre-flight request body
- Stage names and the value that means trading is open
- Scoring formula
- Whether the heartbeat or order routes are idempotent

## Local defaults, not rules

These are engine settings so the mock desk can run. They are not competition fees.

- Flat brokerage INR 15 when `COST_MODEL=synthetic_demo`
- Short collateral 100%
- Short maximum hold 5 simulated days
- Position cap 10%, cash reserve 20%, drawdown stop 8%

`DRY_RUN` defaults to true. `TRADING_ENABLED` defaults to false. The contract client refuses order submission in that state even if a catalog is loaded.
