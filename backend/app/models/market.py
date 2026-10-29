"""Market models built only from a verified catalog mapping."""

from __future__ import annotations

from app.api.models import ContractCatalog, project_message
from app.market.parse import SchemaRejected
from app.models.types import Candle, NewsItem


def candle_from_catalog(catalog: ContractCatalog, topic: str, payload: dict) -> Candle:
    spec = catalog.topic(topic)
    if spec is None:
        raise SchemaRejected(f"no schema for {topic}")
    try:
        projected = project_message(spec, payload)
    except Exception as exc:
        raise SchemaRejected(str(exc)) from exc
    return Candle.model_validate(projected)


def news_from_catalog(catalog: ContractCatalog, topic: str, payload: dict) -> NewsItem:
    spec = catalog.topic(topic)
    if spec is None:
        raise SchemaRejected(f"no schema for {topic}")
    try:
        projected = project_message(spec, payload)
    except Exception as exc:
        raise SchemaRejected(str(exc)) from exc
    if "headline" not in projected:
        raise SchemaRejected("verified news schema does not map a headline")
    return NewsItem.model_validate(projected)
