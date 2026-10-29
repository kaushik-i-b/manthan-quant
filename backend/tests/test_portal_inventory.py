"""Portal inventory from the API reference screenshot.

The mock bodies are placeholders. They are not the competition JSON.
"""

import httpx
import pytest

from app.api.errors import SchemaNotConfigured
from app.api.inventory import ENDPOINTS, STAGE_LABELS, local_portal_panel, orders_allowed_stage, unresolved_mock
from app.config import Settings
from app.execution.client import TradingApiClient
from app.execution.rate_limit import RateLimiter


def test_inventory_matches_the_portal_page() -> None:
    found = {(item.method, item.path) for item in ENDPOINTS}
    assert found == {
        ("POST", "/orders"),
        ("GET", "/orders"),
        ("GET", "/portfolio"),
        ("GET", "/portfolio/cash"),
        ("GET", "/stocks"),
        ("GET", "/stocks/history"),
        ("GET", "/simulation/clock"),
        ("GET", "/stage"),
        ("POST", "/bot/heartbeat"),
    }
    assert "development" in STAGE_LABELS
    history = next(item for item in ENDPOINTS if item.path == "/stocks/history")
    assert history.query_parameters == ("ticker", "start_date", "end_date", "days")
    assert all(item.schema_status == "unresolved" for item in ENDPOINTS)


def test_stage_permission_and_mock_body_are_not_invented() -> None:
    with pytest.raises(SchemaNotConfigured):
        orders_allowed_stage("simulation")
    mock = unresolved_mock("GET", "/portfolio/cash")
    assert mock["official"] is False
    assert mock["schema_status"] == "unresolved"
    assert "cash" not in mock
    assert mock["path"] == "/api/v1/portfolio/cash"
    portfolio = unresolved_mock("GET", "/portfolio")
    assert portfolio["documented_identifiers"] == ["quantity", "is_short", "market_value", "unrealized_pnl"]


def test_local_panel_labels_simulator_analogs() -> None:
    panel = local_portal_panel(sim_day=80, total_days=160, interval_seconds=2.5, cash=1000.0)
    assert panel["bot_auth"] == "unresolved"
    assert panel["clock"]["schema_status"] == "unresolved"
    assert panel["clock"]["local_simulator"]["remaining_days"] == 79
    assert panel["cash"]["local_simulator_cash"] == 1000.0
    assert panel["history_path"] == "GET /api/v1/stocks/history"


@pytest.mark.asyncio
async def test_history_uses_query_parameters_not_a_ticker_path() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.url.query.decode()))
        return httpx.Response(200, json={"schema_status": "unresolved"})

    settings = Settings(bot_access_token="secret-token", api_timeout_sec=1, dry_run=True, trading_enabled=False)
    client = TradingApiClient(settings, RateLimiter(20), transport=httpx.MockTransport(handler))
    try:
        await client.get_history("INFY", start_date="2020-01-01", end_date="2024-12-31", days=30)
        await client.get_simulation_clock()
        await client.get_portfolio_cash()
    finally:
        await client.aclose()
    history = seen[0]
    assert history[0].endswith("/stocks/history")
    assert "/stocks/INFY/history" not in history[0]
    assert "ticker=INFY" in history[1]
    assert "start_date=2020-01-01" in history[1]
    assert "end_date=2024-12-31" in history[1]
    assert "days=30" in history[1]
    assert seen[1][0].endswith("/simulation/clock")
    assert seen[2][0].endswith("/portfolio/cash")
