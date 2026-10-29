"""Bearer authentication for the trading API.

The token is read from the environment by Settings. This module never
prints it and never accepts a token as a logged argument.
"""

from __future__ import annotations

import re

from app.api.errors import SchemaNotConfigured

_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-+/=]+")
_JWT = re.compile(r"eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*")
_PASSWORD_JSON = re.compile(r'(?i)("password"\s*:\s*")[^"]*"')


def bearer_headers(token: str) -> dict[str, str]:
    cleaned = token.strip()
    if not cleaned:
        raise SchemaNotConfigured("BOT_ACCESS_TOKEN is empty")
    return {"Authorization": f"Bearer {cleaned}", "Accept": "application/json"}


def redact(text: str) -> str:
    """Remove bearer tokens, JWTs, and JSON password fields from a string."""
    cleaned = _BEARER.sub("Bearer ***", text)
    cleaned = _JWT.sub("***", cleaned)
    cleaned = _PASSWORD_JSON.sub(r'\1***"', cleaned)
    return cleaned
