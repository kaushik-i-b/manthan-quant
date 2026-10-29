# Authentication

## Portal login

The participant portal is `http://192.168.65.157:3003`. The username for the venue extractor is `MN2615`.

The password is only `MANTHAN_PORTAL_PASSWORD` in the environment. The extractor in `scripts/extract_portal_contracts.py` reads that variable and does not write it to disk. This machine did not have the variable set, and the portal did not accept a TCP connection, so no session was created.

## Trading API

The build brief says the trading API uses a bearer token. The engine reads it from `BOT_ACCESS_TOKEN` on the server. Logs pass through `redact` in `backend/app/api/auth.py` and the JSON log formatter, which replaces bearer values and password fields.

The token is not a frontend environment variable. The desk talks to the local engine. Pause and resume use `CONTROL_TOKEN`, which is a local control secret, not the venue token.

No portal session cookie and no access token were captured on 29 October 2026. Header names beyond `Authorization: Bearer` were not confirmed.

## Status

| Item | Status |
| --- | --- |
| Portal password handling | VERIFIED as an environment variable in the extractor. Login itself was not run |
| Bearer header for the trading API | INFERRED from the build brief |
| Token endpoint, expiry, and refresh | MISSING |
| Kafka authentication | MISSING |
