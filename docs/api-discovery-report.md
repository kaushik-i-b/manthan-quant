# API discovery report

Date of this attempt: 29 October 2026, from the cloud build environment (not the competition Wi-Fi).

## Reachability

| Target | Result | Status |
| --- | --- | --- |
| `http://192.168.65.157:3003` | HTTP timed out after 5 seconds | MISSING |
| `http://192.168.65.157:3002/api/v1/stage` | HTTP timed out after 5 seconds | MISSING |
| TCP `192.168.65.157:3003`, `:3002`, `:9094` | connect failed (errno 11) | MISSING |

`MANTHAN_PORTAL_PASSWORD` was unset, so no login was attempted. The username supplied for the venue script is `MN2615`. It was not sent anywhere.

This environment cannot open the private portal. No page, OpenAPI file, Kafka example, or trading-rule table was read from it.

## What was not done

- No login.
- No heartbeat POST.
- No order POST.
- No account changes.
- No tokens or cookies were stored.

## How to extract on the venue Wi-Fi

```bash
pip install -r scripts/requirements-portal.txt
python -m playwright install chromium
export MANTHAN_PORTAL_PASSWORD='the portal password'
python scripts/extract_portal_contracts.py
```

The script writes `var/portal-extract/`, which is gitignored. It redacts lines that look like passwords, bearer tokens, or cookies. It does not submit orders. If it finds an OpenAPI or Swagger JSON document, that file can be converted with `catalog_from_openapi` in `backend/app/api/models.py`. Prose pages are saved as text and are not turned into field lists.

A later uploaded screenshot of the portal API reference supplied the path inventory below. JSON bodies are still unresolved, so the engine still will not build a venue payload.

## Endpoint inventory from the uploaded portal screenshot

The page "API REFERENCE & INTERACTIVE CONSOLE" lists nine endpoints. Paths are VERIFIED. JSON schemas are unresolved. The earlier guess `GET /api/v1/stocks/{ticker}/history` is withdrawn.

| Method | Path | Schema |
| --- | --- | --- |
| POST | `/api/v1/orders` | unresolved; optional identifier `date` is named |
| GET | `/api/v1/orders` | unresolved |
| GET | `/api/v1/portfolio` | unresolved; `quantity`, `is_short`, `market_value`, `unrealized_pnl` are named |
| GET | `/api/v1/portfolio/cash` | unresolved |
| GET | `/api/v1/stocks` | unresolved |
| GET | `/api/v1/stocks/history` | unresolved; query names `ticker`, `start_date`, `end_date`, `days` are VERIFIED |
| GET | `/api/v1/simulation/clock` | unresolved |
| GET | `/api/v1/stage` | unresolved; labels development, ready, preflight, simulation are named |
| POST | `/api/v1/bot/heartbeat` | unresolved; identifier `seq` is named |

No expanded OpenAPI operation, example body, or status-code table was in the screenshot.

## Kafka inventory

| Item | Status |
| --- | --- |
| Broker `192.168.65.157:9094` | INFERRED from the build brief |
| Topics `market.ticks`, `market.news` | INFERRED from the build brief |
| Authentication | MISSING |
| Consumer group name | MISSING |
| Partition count | MISSING |
| Encoding | MISSING |
| Tick fields | MISSING |
| News fields | MISSING |
| Example messages | MISSING |

## Ambiguities

The build brief described a bearer token. The portal console uses a cookie named `access_token`. Which transport the bot must use is unresolved. The brief also did not show `GET /portfolio`, `GET /portfolio/cash`, `GET /orders`, or `GET /simulation/clock`; those paths are now taken from the portal page. Kafka message fields are still missing. No contradiction inside the screenshot itself was found.
