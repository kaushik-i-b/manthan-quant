"""Contract catalog.

Field lists come from an OpenAPI document or from a portal extract file.
Nothing in this module adds a venue field that was not in that source.
A catalog whose source is not ``portal`` cannot be used for a live submission.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.api.errors import SchemaNotConfigured

Status = Literal["verified", "inferred", "missing"]
PY_TYPES = {"string": str, "number": float, "integer": int, "boolean": bool}


class FieldSpec(BaseModel):
    name: str
    type: str = "string"
    required: bool = False
    status: Status = "missing"
    location: str = "body"
    constraints: str = ""
    source: str = ""
    maps_to: str = ""


class EndpointSpec(BaseModel):
    method: str
    path: str
    purpose: str = ""
    status: Status = "missing"
    auth: str = ""
    source_page: str = ""
    request_fields: list[FieldSpec] = Field(default_factory=list)
    response_fields: list[FieldSpec] = Field(default_factory=list)
    query_fields: list[FieldSpec] = Field(default_factory=list)
    success_statuses: list[int] = Field(default_factory=list)
    error_statuses: list[int] = Field(default_factory=list)
    rate_limit: str = ""
    notes: str = ""


class KafkaTopicSpec(BaseModel):
    name: str
    status: Status = "missing"
    encoding: str = ""
    source_page: str = ""
    fields: list[FieldSpec] = Field(default_factory=list)
    partition_count: int | None = None
    notes: str = ""


class RuleSpec(BaseModel):
    name: str
    value: str
    status: Status = "missing"
    source_page: str = ""


class ContractCatalog(BaseModel):
    source: str = "empty"
    extracted_at: str = ""
    portal_url: str = ""
    reachable: bool = False
    endpoints: list[EndpointSpec] = Field(default_factory=list)
    kafka_topics: list[KafkaTopicSpec] = Field(default_factory=list)
    rules: list[RuleSpec] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)

    def official(self) -> bool:
        return self.source == "portal" and self.reachable

    def endpoint(self, method: str, path: str) -> EndpointSpec | None:
        method = method.upper()
        for item in self.endpoints:
            if item.method.upper() == method and item.path == path:
                return item
        return None

    def topic(self, name: str) -> KafkaTopicSpec | None:
        for item in self.kafka_topics:
            if item.name == name:
                return item
        return None


def empty_catalog() -> ContractCatalog:
    return ContractCatalog(source="empty", reachable=False)


def load_catalog(path: str | Path | None) -> ContractCatalog:
    if not path:
        return empty_catalog()
    file = Path(path)
    if not file.is_file():
        return empty_catalog()
    return ContractCatalog.model_validate(json.loads(file.read_text(encoding="utf-8")))


def serialize_body(
    endpoint: EndpointSpec,
    values: dict[str, Any],
    *,
    catalog: ContractCatalog,
    allow_unofficial: bool = False,
) -> dict[str, Any]:
    """Build a JSON body from verified fields only."""
    if endpoint.status != "verified":
        raise SchemaNotConfigured(f"{endpoint.method} {endpoint.path} is not a verified contract")
    if not catalog.official() and not allow_unofficial:
        raise SchemaNotConfigured("contract catalog is not an official portal extract")
    body: dict[str, Any] = {}
    for field in endpoint.request_fields:
        if field.location not in {"body", ""}:
            continue
        if field.status != "verified":
            continue
        if field.name not in values:
            if field.required:
                raise SchemaNotConfigured(f"missing required field {field.name}")
            continue
        body[field.name] = _coerce(field, values[field.name])
    return body


def project_message(topic: KafkaTopicSpec, payload: dict[str, Any]) -> dict[str, Any]:
    """Map a Kafka object onto canonical candle/news keys using verified maps_to."""
    if topic.status != "verified":
        raise SchemaNotConfigured(f"kafka topic {topic.name} is not verified")
    projected: dict[str, Any] = {}
    for field in topic.fields:
        if field.status != "verified" or not field.maps_to:
            continue
        if field.name not in payload:
            if field.required:
                raise SchemaNotConfigured(f"kafka message missing {field.name}")
            continue
        projected[field.maps_to] = payload[field.name]
    required = {"ticker", "sim_day", "open", "high", "low", "close", "volume"}
    if topic.name.endswith("ticks") or "tick" in topic.name:
        missing = required - projected.keys()
        if missing:
            raise SchemaNotConfigured(
                "verified tick schema does not map every candle field: " + ", ".join(sorted(missing))
            )
    return projected


def _coerce(field: FieldSpec, value: Any) -> Any:
    py = PY_TYPES.get(field.type)
    if py is None or value is None:
        return value
    if py is bool:
        return bool(value)
    if py is int and isinstance(value, bool):
        raise SchemaNotConfigured(f"{field.name} is not an integer")
    try:
        return py(value)
    except (TypeError, ValueError) as exc:
        raise SchemaNotConfigured(f"{field.name} is not {field.type}") from exc


def catalog_from_openapi(spec: dict[str, Any], *, source_page: str) -> ContractCatalog:
    """Copy an OpenAPI document into a catalog. Unknown shapes stay unmapped."""
    components = spec.get("components", {}).get("schemas", {})
    endpoints: list[EndpointSpec] = []
    ambiguities: list[str] = []
    security = spec.get("security") or []
    auth = "bearer" if _security_is_bearer(spec, security) else ""
    for path, methods in (spec.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                continue
            request_fields, query_fields, notes = _operation_fields(operation, components, ambiguities, path)
            response_fields = _response_fields(operation, components, ambiguities, path)
            success, errors = _statuses(operation)
            endpoints.append(
                EndpointSpec(
                    method=method.upper(),
                    path=path,
                    purpose=str(operation.get("summary") or operation.get("operationId") or ""),
                    status="verified",
                    auth=auth or _operation_auth(spec, operation),
                    source_page=source_page,
                    request_fields=request_fields,
                    response_fields=response_fields,
                    query_fields=query_fields,
                    success_statuses=success,
                    error_statuses=errors,
                    notes=notes,
                )
            )
    return ContractCatalog(
        source="portal",
        reachable=True,
        portal_url=source_page,
        endpoints=endpoints,
        ambiguities=ambiguities,
    )


def _security_is_bearer(spec: dict, security: list) -> bool:
    schemes = spec.get("components", {}).get("securitySchemes", {})
    names = set()
    for item in security:
        if isinstance(item, dict):
            names.update(item)
    for name in names:
        scheme = schemes.get(name) or {}
        if str(scheme.get("scheme", "")).lower() == "bearer" or scheme.get("type") == "http":
            return True
    return False


def _operation_auth(spec: dict, operation: dict) -> str:
    if _security_is_bearer(spec, operation.get("security") or []):
        return "bearer"
    return ""


def _response_fields(operation: dict, components: dict, ambiguities: list[str], path: str) -> list[FieldSpec]:
    fields: list[FieldSpec] = []
    for code, response in (operation.get("responses") or {}).items():
        if not str(code).isdigit() or not (200 <= int(code) < 300) or not isinstance(response, dict):
            continue
        schema = ((response.get("content") or {}).get("application/json") or {}).get("schema")
        if not isinstance(schema, dict):
            continue
        resolved, note = _resolve(schema, components)
        if note:
            ambiguities.append(f"{path} response: {note}")
        required = set(resolved.get("required") or [])
        for name, item in (resolved.get("properties") or {}).items():
            fields.append(
                FieldSpec(
                    name=str(name),
                    type=_schema_type(item if isinstance(item, dict) else {}),
                    required=name in required,
                    status="verified",
                    location="response",
                    source=path,
                )
            )
    return fields


def _statuses(operation: dict) -> tuple[list[int], list[int]]:
    success: list[int] = []
    errors: list[int] = []
    for code in (operation.get("responses") or {}):
        if not str(code).isdigit():
            continue
        number = int(code)
        if 200 <= number < 300:
            success.append(number)
        else:
            errors.append(number)
    return success, errors


def _operation_fields(operation: dict, components: dict, ambiguities: list[str], path: str):
    request_fields: list[FieldSpec] = []
    query_fields: list[FieldSpec] = []
    notes: list[str] = []
    for param in operation.get("parameters") or []:
        if not isinstance(param, dict):
            continue
        location = str(param.get("in") or "query")
        spec = FieldSpec(
            name=str(param.get("name") or ""),
            type=_schema_type(param.get("schema") or {}),
            required=bool(param.get("required")),
            status="verified",
            location=location,
            source=path,
        )
        if location == "query":
            query_fields.append(spec)
        elif location == "path":
            request_fields.append(spec)
    body = operation.get("requestBody") or {}
    content = body.get("content") or {}
    json_schema = (content.get("application/json") or {}).get("schema")
    if json_schema:
        resolved, note = _resolve(json_schema, components)
        if note:
            notes.append(note)
            ambiguities.append(f"{path}: {note}")
        required = set(resolved.get("required") or [])
        properties = resolved.get("properties") or {}
        if resolved.get("type") not in {None, "object"} or (not properties and resolved):
            if not properties:
                ambiguities.append(f"{path}: request schema has no listed properties")
        for name, schema in properties.items():
            request_fields.append(
                FieldSpec(
                    name=str(name),
                    type=_schema_type(schema if isinstance(schema, dict) else {}),
                    required=name in required,
                    status="verified",
                    location="body",
                    source=path,
                )
            )
    return request_fields, query_fields, " ".join(notes)


def _resolve(schema: dict, components: dict) -> tuple[dict, str]:
    if "$ref" in schema:
        name = str(schema["$ref"]).split("/")[-1]
        target = components.get(name)
        if not isinstance(target, dict):
            return {}, f"unresolved $ref {schema['$ref']}"
        return _resolve(target, components)
    if "allOf" in schema:
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for part in schema["allOf"]:
            if not isinstance(part, dict):
                continue
            resolved, _note = _resolve(part, components)
            merged["properties"].update(resolved.get("properties") or {})
            merged["required"].extend(resolved.get("required") or [])
        return merged, ""
    return schema, ""


def _schema_type(schema: dict) -> str:
    kind = str(schema.get("type") or "string")
    if kind == "array":
        return "array"
    if kind in PY_TYPES or kind == "object":
        return kind
    return "string"
