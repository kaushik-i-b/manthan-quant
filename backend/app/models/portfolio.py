"""Portfolio figures copied from a verified response field list.

Unlisted keys are ignored. Missing required keys make the snapshot unusable
instead of being filled with guesses.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.api.errors import SchemaNotConfigured
from app.api.models import ContractCatalog


class PortfolioSnapshot(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    source_page: str = ""
    verified: bool = False


def portfolio_from_response(catalog: ContractCatalog, path: str, payload: dict[str, Any]) -> PortfolioSnapshot:
    endpoint = catalog.endpoint("GET", path)
    if endpoint is None or endpoint.status != "verified":
        raise SchemaNotConfigured(f"no verified portfolio contract for GET {path}")
    if not catalog.official():
        raise SchemaNotConfigured("portfolio catalog is not an official portal extract")
    kept: dict[str, Any] = {}
    for field in endpoint.response_fields:
        if field.status != "verified":
            continue
        if field.name not in payload:
            if field.required:
                raise SchemaNotConfigured(f"portfolio response missing {field.name}")
            continue
        kept[field.name] = payload[field.name]
    return PortfolioSnapshot(fields=kept, source_page=endpoint.source_page, verified=True)
