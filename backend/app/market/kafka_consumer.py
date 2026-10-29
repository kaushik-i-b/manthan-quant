"""Kafka validation against a portal catalog.

The consumer does not connect unless a group id and a verified topic schema
are both configured. Parsing never invents fields.
"""

from __future__ import annotations

from typing import Any

from app.api.errors import SchemaNotConfigured
from app.api.models import ContractCatalog, project_message
from app.config import Settings
from app.market.parse import SchemaRejected, loads


def require_consumer(settings: Settings, catalog: ContractCatalog) -> None:
    if not settings.kafka_group_id.strip():
        raise SchemaNotConfigured("Kafka consumer group is not configured")
    if not catalog.official():
        raise SchemaNotConfigured("Kafka schemas are not from a portal extract")


def parse_topic_message(catalog: ContractCatalog, topic: str, raw: bytes | str) -> dict[str, Any]:
    spec = catalog.topic(topic)
    if spec is None or spec.status != "verified":
        raise SchemaRejected(f"no verified schema for topic {topic}")
    if not catalog.official():
        raise SchemaRejected("kafka catalog is not an official portal extract")
    payload = loads(raw)
    try:
        return project_message(spec, payload)
    except SchemaNotConfigured as exc:
        raise SchemaRejected(str(exc)) from exc
