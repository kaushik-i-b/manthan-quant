"""Order bodies built only from verified request fields."""

from __future__ import annotations

from typing import Any

from app.api.models import ContractCatalog, serialize_body


def order_body(catalog: ContractCatalog, path: str, values: dict[str, Any], *, allow_unofficial: bool = False) -> dict:
    endpoint = catalog.endpoint("POST", path)
    if endpoint is None:
        from app.api.errors import SchemaNotConfigured

        raise SchemaNotConfigured(f"no contract for POST {path}")
    return serialize_body(endpoint, values, catalog=catalog, allow_unofficial=allow_unofficial)
