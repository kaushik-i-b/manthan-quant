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

Until that file exists, every contract below is MISSING and the engine will not build a venue payload from a guessed schema.

## Endpoint inventory

| Method | Path | Status | Source |
| --- | --- | --- | --- |
| GET | `/api/v1/stocks` | INFERRED from the build brief only | not the portal |
| GET | `/api/v1/stocks/{ticker}/history` | INFERRED from the build brief only | not the portal |
| GET | `/api/v1/stage` | INFERRED from the build brief only | not the portal |
| POST | `/api/v1/bot/heartbeat` | INFERRED from the build brief only | body MISSING |
| POST | `/api/v1/orders` | INFERRED from the build brief only | body MISSING |
| Portfolio, cash, holdings, order history, order status | not named with a path in the brief | MISSING | portal unread |

Request fields, response fields, status codes, and examples for every row are MISSING.

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

The build brief and the unread portal may disagree. No portal text was available to compare, so no contradiction was resolved.
