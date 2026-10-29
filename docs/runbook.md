# Runbook

## Local demo

1. `make install`
2. `make demo`
3. Open http://127.0.0.1:8742
4. Confirm the amber banner says the tape is synthetic and the mode pill says `DRY_RUN`.
5. Watch the lamp move PREFLIGHT → LIVE.
6. On Risk, **Pause trading** must return `ack: true` before the lamp shows PAUSED. Resume the same way.
7. **Simulate feed outage** flips the feed to interrupted, then back. New entries are blocked while the feed is stale.

## Switching to the venue

Do this only on the competition network, after the PDFs are in hand.

1. Fill the template files and point `VENUE_*_PATH` and `VENUE_STAGE_*` at them.
2. Set `KAFKA_GROUP_ID` to the official consumer group. Leave `KAFKA_ENABLED=false` until a captured message matches the template.
3. Export `BOT_ACCESS_TOKEN` in the environment. Do not put it in the frontend.
4. `python scripts/check_venue.py` should print a status code. Do not trade on that alone.
5. Keep `DRY_RUN=true` for a session that only heartbeats and reads `/stage`.
6. Arm orders only with `MARKET_MODE=venue`, `DRY_RUN=false`, `TRADING_ENABLED=true`, and `CONFIRM_LIVE_TRADING=I_UNDERSTAND`.

If an order times out, the ticker freezes. Do not retry it. Reconcile from the venue's own order history once that endpoint is documented, then clear the freeze in code only after the fill is known.

## Rate limit

The client stops at 120 requests/minute including heartbeats and stage polls. Mock mode does not spend that budget. The execution page shows used/remaining and says when the budget is unused.

## Failure modes

| Symptom | Meaning |
| --- | --- |
| Lamp HALTED, heartbeat failing | Venue payload missing or POST failed. No orders. |
| Stage UNKNOWN | Stage field not configured, or the response did not match. |
| Feed interrupted | Demo outage or stale tape. Entries blocked. |
| Order UNKNOWN | Venue response could not be parsed, or the call timed out. Ticker frozen. |
| Desk "Engine offline" | Backend not on port 8741. The page does not invent numbers. |
