# Authentication

## Portal login

The participant portal is `http://192.168.65.157:3003`. The username for the venue extractor is `MN2615`.

The password is only `MANTHAN_PORTAL_PASSWORD` in the environment. The extractor in `scripts/extract_portal_contracts.py` reads that variable and does not write it to disk. This machine did not have the variable set, and the portal did not accept a TCP connection, so no session was created.

## Trading API

The portal's interactive console says requests use the active session token from `document.cookie`. The page labels that control COOKIE AUTH and shows a cookie named `access_token`. The token value in the screenshot was truncated and is not stored here.

The page does not say whether a bot must send that cookie, an `Authorization: Bearer` header, or both. The build brief said bearer. Those two statements are not resolved. `bot_auth` in the desk snapshot stays `unresolved`. `BOT_ACCESS_TOKEN` remains a server-only setting and is redacted in logs. The desk does not receive it.

Pause and resume use `CONTROL_TOKEN`, a local control secret, not the venue token.

## Status

| Item | Status |
| --- | --- |
| Portal console cookie name `access_token` | VERIFIED from the API reference screenshot |
| Bot transport (cookie versus bearer) | unresolved |
| Token endpoint, expiry, and refresh | MISSING |
| Kafka authentication | MISSING |
