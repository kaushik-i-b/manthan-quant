"""Kafka payload parsing.

The internal schema is accepted for the mock producer and tests. Any other
payload is rejected unless the operator supplies an explicit field map.
Rejected messages are not turned into trades.
"""

from __future__ import annotations

import json
from typing import Any

from app.models.types import Candle, NewsItem

INTERNAL_TICK = "manthan-quant.internal.tick.v1"
INTERNAL_NEWS = "manthan-quant.internal.news.v1"


class SchemaRejected(ValueError):
    pass


def loads(raw: bytes | str) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SchemaRejected("payload is not a JSON object")
    return data


def parse_tick(data: dict, field_map: dict | None = None) -> Candle:
    schema = data.get("schema") or data.get("schema_name")
    if schema == INTERNAL_TICK:
        return Candle.model_validate(data)
    if field_map:
        return Candle.model_validate(_project(data, field_map, "tick"))
    raise SchemaRejected(
        "tick schema is not manthan-quant.internal.tick.v1 and no venue field map is configured"
    )


def parse_news(data: dict, field_map: dict | None = None) -> NewsItem:
    schema = data.get("schema") or data.get("schema_name")
    if schema == INTERNAL_NEWS:
        return NewsItem.model_validate(data)
    if field_map:
        return NewsItem.model_validate(_project(data, field_map, "news"))
    raise SchemaRejected(
        "news schema is not manthan-quant.internal.news.v1 and no venue field map is configured"
    )


def _project(data: dict, field_map: dict, kind: str) -> dict[str, Any]:
    try:
        projected = {dest: data[src] for dest, src in field_map.items()}
    except KeyError as exc:
        raise SchemaRejected(f"{kind} field map missing source {exc}") from exc
    return projected


async def consume_decoded(messages: list[dict], handler, commit) -> dict:
    """Testable consume loop. Commits after a successful handle, and also
    commits a schema rejection so a poison message cannot stall the group.
    The handler is responsible for duplicate suppression.
    """
    handled = 0
    rejected = 0
    for message in messages:
        try:
            await handler(message)
            handled += 1
        except SchemaRejected:
            rejected += 1
        await commit(message)
    return {"handled": handled, "rejected": rejected}
