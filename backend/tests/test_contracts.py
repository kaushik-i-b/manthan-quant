"""Contract catalog tests.

The OpenAPI document in fixtures is a unit-test sample. It is not the
MANTHAN portal schema, and passing these tests does not verify live integration.
"""

import json
from pathlib import Path

import httpx
import pytest

from app.api.auth import bearer_headers, redact
from app.api.client import ContractClient
from app.api.errors import ApiError, SchemaNotConfigured
from app.api.models import (
    ContractCatalog,
    EndpointSpec,
    FieldSpec,
    KafkaTopicSpec,
    catalog_from_openapi,
    empty_catalog,
    serialize_body,
)
from app.config import Settings
from app.execution.rate_limit import RateLimiter
from app.market.kafka_consumer import parse_topic_message, require_consumer
from app.market.parse import SchemaRejected
from app.models.orders import order_body
from app.models.portfolio import portfolio_from_response

FIXTURE = Path(__file__).parent / "fixtures" / "openapi_sample.json"


def _settings(**overrides) -> Settings:
    base = dict(
        market_mode="mock",
        dry_run=True,
        trading_enabled=False,
        bot_access_token="test-token-not-real",
        database_path="",
    )
    base.update(overrides)
    return Settings(**base)


def test_empty_catalog_refuses_an_order_body() -> None:
    catalog = empty_catalog()
    with pytest.raises(SchemaNotConfigured):
        order_body(catalog, "/api/v1/orders", {"ticker": "RELIANCE", "quantity": 1})


def test_openapi_sample_serializes_only_verified_fields() -> None:
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    catalog = catalog_from_openapi(spec, source_page="unit-test://openapi_sample.json")
    catalog = catalog.model_copy(update={"source": "unit_test", "reachable": False})
    endpoint = catalog.endpoint("POST", "/orders")
    assert endpoint is not None
    body = serialize_body(
        endpoint,
        {"symbol": "INFY", "side": "BUY", "qty": "3", "note": "skip-me-if-optional-wait"},
        catalog=catalog,
        allow_unofficial=True,
    )
    assert body == {"symbol": "INFY", "side": "BUY", "qty": 3, "note": "skip-me-if-optional-wait"}
    with pytest.raises(SchemaNotConfigured):
        serialize_body(endpoint, {"symbol": "INFY"}, catalog=catalog, allow_unofficial=True)
    with pytest.raises(SchemaNotConfigured):
        serialize_body(endpoint, {"symbol": "INFY", "side": "BUY", "qty": 1}, catalog=catalog, allow_unofficial=False)


def test_bearer_header_is_redacted_in_text() -> None:
    headers = bearer_headers("super-secret-token")
    assert headers["Authorization"] == "Bearer super-secret-token"
    logged = redact(f"sent {headers['Authorization']} and {{\"password\": \"hunter2\"}}")
    assert "super-secret-token" not in logged
    assert "hunter2" not in logged
    assert "Bearer ***" in logged
    with pytest.raises(SchemaNotConfigured):
        bearer_headers("  ")


@pytest.mark.asyncio
async def test_contract_client_does_not_send_orders_in_dry_run() -> None:
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    catalog = catalog_from_openapi(spec, source_page="unit-test://openapi_sample.json")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("dry run must not call the venue")

    transport = httpx.MockTransport(handler)
    client = ContractClient(_settings(), catalog, transport=transport, allow_unofficial=True)
    try:
        with pytest.raises(SchemaNotConfigured):
            await client.submit("POST", "/orders", {"symbol": "INFY", "side": "BUY", "qty": 1})
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_contract_client_retries_get_and_stops_on_rate_limit() -> None:
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    catalog = catalog_from_openapi(spec, source_page="unit-test://openapi_sample.json")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.headers["Authorization"] == "Bearer test-token-not-real"
        if calls["n"] < 2:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json={"cash": 10})

    transport = httpx.MockTransport(handler)
    client = ContractClient(
        _settings(),
        catalog,
        limiter=RateLimiter(2),
        transport=transport,
        allow_unofficial=True,
    )
    try:
        body = await client.get_json("/portfolio")
        assert body["cash"] == 10
        with pytest.raises(ApiError) as caught:
            await client.get_json("/portfolio")
        assert caught.value.kind == "rate_limit"
    finally:
        await client.aclose()


def test_kafka_schema_rejects_until_a_portal_catalog_maps_fields() -> None:
    settings = _settings(kafka_group_id="")
    with pytest.raises(SchemaNotConfigured):
        require_consumer(settings, empty_catalog())
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    catalog = catalog_from_openapi(spec, source_page="unit-test://openapi_sample.json")
    catalog.kafka_topics.append(
        KafkaTopicSpec(
            name="market.ticks",
            status="verified",
            fields=[
                FieldSpec(name="sym", type="string", required=True, status="verified", maps_to="ticker"),
                FieldSpec(name="day", type="integer", required=True, status="verified", maps_to="sim_day"),
            ],
        )
    )
    with pytest.raises(SchemaRejected):
        parse_topic_message(catalog, "market.ticks", b'{"sym":"TCS","day":1}')
    official = catalog.model_copy(update={"source": "portal", "reachable": True})
    with pytest.raises(SchemaRejected):
        parse_topic_message(official, "market.ticks", b'{"sym":"TCS","day":1}')


def test_portfolio_snapshot_drops_unknown_keys() -> None:
    catalog = ContractCatalog(
        source="portal",
        reachable=True,
        endpoints=[
            EndpointSpec(
                method="GET",
                path="/portfolio",
                status="verified",
                source_page="unit-test",
                response_fields=[
                    FieldSpec(name="cash", type="number", required=True, status="verified"),
                    FieldSpec(name="comment", type="string", required=False, status="inferred"),
                ],
            )
        ],
    )
    snap = portfolio_from_response(catalog, "/portfolio", {"cash": 5, "comment": "ignore", "extra": 1})
    assert snap.fields == {"cash": 5}
    assert snap.verified is True
