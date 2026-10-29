"""Endpoint inventory copied from the participant portal API reference.

The source is a screenshot of the portal page titled "API REFERENCE &
INTERACTIVE CONSOLE", printed 10/29/26, 10:49 PM. Only paths, methods, and
identifiers that appear in that page are recorded. JSON request and response
schemas were not on the page and stay unresolved.

This module does not authorize order submission.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.api.errors import SchemaNotConfigured


@dataclass(frozen=True)
class EndpointRecord:
    method: str
    path: str
    category: str
    summary: str
    # Identifiers printed as names, not a JSON schema.
    documented_identifiers: tuple[str, ...] = ()
    query_parameters: tuple[str, ...] = ()
    schema_status: str = "unresolved"


# Paths are relative to the API root. The client base URL already includes /api/v1.
ENDPOINTS: tuple[EndpointRecord, ...] = (
    EndpointRecord(
        "POST",
        "/orders",
        "Trading & Orders",
        "Submit a BUY, SELL, SHORT, or COVER market order. Optional date records the decision market date and does not change the execution price.",
        documented_identifiers=("date", "BUY", "SELL", "SHORT", "COVER"),
    ),
    EndpointRecord(
        "GET",
        "/orders",
        "Trading & Orders",
        "Historical order audit logs, execution fill prices, rejection reasons, and timestamps.",
    ),
    EndpointRecord(
        "GET",
        "/portfolio",
        "Trading & Orders",
        "Cash reserve, long and short holdings, mark-to-market valuation, and realized and unrealized P&L. Short quantity is negative, is_short is true, and market_value is a negative liability.",
        documented_identifiers=("quantity", "is_short", "market_value", "unrealized_pnl"),
    ),
    EndpointRecord(
        "GET",
        "/portfolio/cash",
        "Trading & Orders",
        "Lightweight cash balance query for position sizing.",
    ),
    EndpointRecord(
        "GET",
        "/stocks",
        "Market Data & Prices",
        "Authenticated stock list for the active simulation, including READY and PRE-FLIGHT, with ticker, masked company name, and a short description.",
        documented_identifiers=("ticker",),
    ),
    EndpointRecord(
        "GET",
        "/stocks/history",
        "Market Data & Prices",
        "Up to 10 years of daily OHLCV strictly prior to the current simulation date unless a range is requested. A range before the listing date returns an error that names the listing date.",
        query_parameters=("ticker", "start_date", "end_date", "days"),
        documented_identifiers=("ticker", "start_date", "end_date", "days"),
    ),
    EndpointRecord(
        "GET",
        "/simulation/clock",
        "Simulation Engine",
        "Current day, total days, remaining days, interval speed, and simulated date.",
    ),
    EndpointRecord(
        "GET",
        "/stage",
        "Simulation Engine",
        "Lifecycle stage, active database, and simulation progress. The page names development, ready, preflight, and simulation.",
        documented_identifiers=("development", "ready", "preflight", "simulation"),
    ),
    EndpointRecord(
        "POST",
        "/bot/heartbeat",
        "Pre-Flight Readiness",
        "Acknowledge the pre-flight standby ping seq received from Kafka.",
        documented_identifiers=("seq",),
    ),
)

STAGE_LABELS: tuple[str, ...] = ("development", "ready", "preflight", "simulation")

# The interactive console reads document.cookie. The bot transport was not specified.
PORTAL_CONSOLE_AUTH = "cookie named access_token"
BOT_AUTH = "unresolved"


def by_path(method: str, path: str) -> EndpointRecord:
    for record in ENDPOINTS:
        if record.method == method.upper() and record.path == path:
            return record
    raise SchemaNotConfigured(f"no portal inventory entry for {method} {path}")


def orders_allowed_stage(label: str) -> None:
    """The page lists stage names and does not say which value permits orders."""
    raise SchemaNotConfigured(
        f"whether stage {label!r} permits orders is not documented; known labels are {', '.join(STAGE_LABELS)}"
    )


def unresolved_mock(method: str, path: str) -> dict:
    """A local stand-in that repeats documented identifiers and no JSON body fields."""
    record = by_path(method, path)
    return {
        "schema_status": record.schema_status,
        "official": False,
        "mock": True,
        "method": record.method,
        "path": "/api/v1" + record.path,
        "documented_identifiers": list(record.documented_identifiers),
        "query_parameters": list(record.query_parameters),
    }


def local_portal_panel(*, sim_day: int, total_days: int, interval_seconds: float, cash: float) -> dict:
    """Local simulator analogs. These keys are not the portal's JSON."""
    remaining = max(total_days - 1 - sim_day, 0)
    return {
        "source_document": "participant portal API reference",
        "bot_auth": BOT_AUTH,
        "portal_console_auth": PORTAL_CONSOLE_AUTH,
        "schema_status": "unresolved",
        "clock": {
            "path": "GET /api/v1/simulation/clock",
            "schema_status": "unresolved",
            "documented_concepts": [
                "current day",
                "total days",
                "remaining days",
                "interval speed",
                "simulated date",
            ],
            "local_simulator": {
                "sim_day": sim_day,
                "total_days": total_days,
                "remaining_days": remaining,
                "interval_seconds": interval_seconds,
            },
        },
        "cash": {
            "path": "GET /api/v1/portfolio/cash",
            "schema_status": "unresolved",
            "documented_concepts": ["cash balance"],
            "local_simulator_cash": cash,
        },
        "history_path": "GET /api/v1/stocks/history",
        "endpoints": [f"{item.method} /api/v1{item.path}" for item in ENDPOINTS],
    }
