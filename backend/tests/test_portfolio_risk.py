"""Portfolio accounting and the independent risk gate."""

import time

import pytest

from app.config import Settings
from app.execution.costs import quote_cost
from app.models.types import Fill, OrderIntent
from app.portfolio.accounting import Portfolio
from app.risk.engine import RiskContext, RiskEngine


def _settings() -> Settings:
    return Settings(cost_model="synthetic_demo", synthetic_brokerage_inr=15, market_mode="mock", dry_run=True)


def _fill(action: str, qty: int, price: float, day: int = 1, ticker: str = "RELIANCE") -> Fill:
    cost = quote_cost(_settings(), qty * price)
    return Fill(
        client_order_id=f"{ticker}-{action}-{day}",
        order_id=f"o-{action}-{day}",
        ticker=ticker,
        action=action,  # type: ignore[arg-type]
        quantity=qty,
        price=price,
        sim_day=day,
        status="FILLED",
        brokerage=cost.brokerage,
        taxes_and_fees=cost.taxes_and_fees,
        venue="mock",
    )


def test_long_round_trip_nets_fees_once() -> None:
    book = Portfolio.start(1000, 1.0)
    book.apply_fill(_fill("BUY", 2, 100))
    assert book.cash == pytest.approx(1000 - 200 - 15)
    assert book.equity({"RELIANCE": 100}) == pytest.approx(1000 - 15)
    book.apply_fill(_fill("SELL", 2, 110, day=2))
    # Gross 20, fees 30, equity 990.
    assert book.equity({}) == pytest.approx(990)
    assert book.closed[0].net_pnl == pytest.approx(-10)
    assert book.equity({}) - book.starting_capital == pytest.approx(book.realized_gross - book.fees_paid)


def test_short_then_cover() -> None:
    book = Portfolio.start(1000, 1.0)
    book.apply_fill(_fill("SHORT", 2, 100))
    assert book.equity({"RELIANCE": 100}) == pytest.approx(985)
    assert book.available_cash() == pytest.approx(1000 - 15)
    book.apply_fill(_fill("COVER", 2, 90, day=2))
    # Gross +20, fees 30.
    assert book.equity({}) == pytest.approx(990)
    assert book.locked_collateral == pytest.approx(0)
    assert book.closed[0].net_pnl == pytest.approx(-10)


def test_duplicate_fill_is_not_applied_twice() -> None:
    book = Portfolio.start(1000, 1.0)
    fill = _fill("BUY", 1, 100)
    book.apply_fill(fill)
    book.apply_fill(fill)
    assert len(book.fills) == 1
    assert book.cash == pytest.approx(1000 - 100 - 15)


def test_risk_blocks_oversized_buy_duplicate_and_bad_stage() -> None:
    settings = _settings()
    engine = RiskEngine(settings)
    book = Portfolio.start(1_000_000, 1.0)
    intent = OrderIntent(
        client_order_id="big",
        ticker="RELIANCE",
        action="BUY",
        quantity=1_000_000_000,
        price=2450,
        sim_day=78,
        strategy="risk_probe",
        reason="probe",
        signal_score=1,
    )
    ctx = RiskContext(
        stage="TRADING",
        heartbeat_fresh=True,
        paused=False,
        data_stale=False,
        portfolio_reliable=True,
        rate_limit_ok=True,
        live_armed=False,
        market_mode="mock",
        marks={"RELIANCE": 2450},
        orders_today=0,
        outstanding=0,
    )
    result = engine.evaluate(intent, book, ctx)
    assert result.approved is False
    assert any("cash" in reason or "position" in reason for reason in result.reasons)

    ctx.stage = "PREFLIGHT"
    blocked = engine.evaluate(
        intent.model_copy(update={"quantity": 1, "client_order_id": "small"}),
        book,
        ctx,
    )
    assert blocked.approved is False
    assert any("stage" in reason for reason in blocked.reasons)

    stale = engine.evaluate(
        intent.model_copy(update={"quantity": 1, "client_order_id": "stale"}),
        book,
        RiskContext(
            stage="TRADING",
            heartbeat_fresh=False,
            paused=False,
            data_stale=False,
            portfolio_reliable=True,
            rate_limit_ok=True,
            live_armed=False,
            market_mode="mock",
            marks={"RELIANCE": 2450},
            orders_today=0,
            outstanding=0,
        ),
    )
    assert any("heartbeat" in reason for reason in stale.reasons)

    seen = RiskContext(
        stage="TRADING",
        heartbeat_fresh=True,
        paused=False,
        data_stale=False,
        portfolio_reliable=True,
        rate_limit_ok=True,
        live_armed=False,
        market_mode="mock",
        marks={"RELIANCE": 2450},
        orders_today=0,
        outstanding=0,
        seen_order_ids={"dup"},
    )
    dup = engine.evaluate(intent.model_copy(update={"quantity": 1, "client_order_id": "dup"}), book, seen)
    assert any("duplicate" in reason for reason in dup.reasons)
    assert time.monotonic() > 0


def test_risk_rejects_sell_without_position_and_short_without_collateral() -> None:
    settings = Settings(
        cost_model="zero",
        market_mode="mock",
        short_collateral_pct=2.0,
        max_position_pct=1,
        max_invested_pct=1,
        min_cash_reserve_pct=0,
        max_drawdown_pct=1,
    )
    engine = RiskEngine(settings)
    book = Portfolio.start(100, 2.0)
    ctx = RiskContext(
        stage="TRADING",
        heartbeat_fresh=True,
        paused=False,
        data_stale=False,
        portfolio_reliable=True,
        rate_limit_ok=True,
        live_armed=False,
        market_mode="mock",
        marks={"T": 50},
        orders_today=0,
        outstanding=0,
    )
    sell = OrderIntent(
        client_order_id="sell",
        ticker="T",
        action="SELL",
        quantity=1,
        price=50,
        sim_day=1,
        strategy="x",
        reason="x",
        signal_score=-1,
        is_exit=True,
    )
    assert engine.evaluate(sell, book, ctx).approved is False
    short = sell.model_copy(update={"action": "SHORT", "client_order_id": "short", "is_exit": False, "quantity": 3})
    # Notional 100, collateral 200, only 100 cash.
    result = engine.evaluate(short, book, ctx)
    assert result.approved is False
    assert any("collateral" in reason for reason in result.reasons)
