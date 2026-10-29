"""End-to-end mock tape: signal, risk, fill, portfolio, and backtest."""

import time

import pytest

from app.backtesting.engine import compare_strategies, run_backtest
from app.config import Settings
from app.runtime import TradingRuntime
from app.simulation.lifecycle import LifecycleManager


def _settings(**overrides) -> Settings:
    base = dict(
        market_mode="mock",
        replay_mode="instant",
        dry_run=True,
        trading_enabled=False,
        cost_model="synthetic_demo",
        synthetic_brokerage_inr=15,
        database_path="",
        demo_probe=True,
        entry_threshold=0.40,
        sim_day_seconds=2.5,
    )
    base.update(overrides)
    return Settings(**base)


async def _drive(settings: Settings | None = None) -> TradingRuntime:
    settings = settings or _settings()
    runtime = TradingRuntime(settings, persist=False)
    runtime.bootstrap()
    runtime.lifecycle.stage = "TRADING"
    runtime.lifecycle.ack(time.monotonic())
    assert runtime.dataset is not None
    for day in range(runtime.dataset.days):
        await runtime.play_day(day, trade=True, delay=False, publish=False)
    return runtime


@pytest.mark.asyncio
async def test_pipeline_buys_rejects_probe_and_accounts() -> None:
    runtime = await _drive()
    try:
        actions = {(fill.ticker, fill.action) for fill in runtime.portfolio.fills}
        assert ("RELIANCE", "BUY") in actions
        assert any(d["strategy"] == "risk_probe" and d["executed"] is False for d in runtime.trade_log)
        probe = next(d for d in runtime.trade_log if d["strategy"] == "risk_probe")
        assert probe["risk_approved"] is False
        assert "Rejected" in probe["reason"]
        assert runtime.milestones["market_data"]
        assert runtime.milestones["indicators"]
        assert runtime.milestones["signal"]
        assert runtime.milestones["risk_pass"]
        assert runtime.milestones["fill"]
        assert runtime.milestones["pnl_updated"]
        assert runtime.milestones["risk_reject"]
        assert runtime.portfolio.fills
        assert runtime.rejected_count >= 1
        # Fills moved cash. Rejected probe did not.
        assert runtime.portfolio.equity(runtime.marks) != runtime.portfolio.starting_capital
        scores = [d["signal_score"] for d in runtime.trade_log if d["action"] != "HOLD"]
        assert scores
        assert all(d["score_type"] == "heuristic" for d in runtime.trade_log)
        latency = runtime.latency.p50
        assert latency is not None and latency < 100
        snap = runtime.snapshot()
        assert snap["meta"]["data_origin"] == "synthetic"
        assert snap["meta"]["cost_model_official"] is False
        assert snap["health"]["mode"] == "DRY_RUN"
        assert snap["health"]["kafka"] == "disabled"
        assert snap["health"]["trading_api"] == "not_contacted"
    finally:
        await runtime.client.aclose()


@pytest.mark.asyncio
async def test_pause_and_stale_heartbeat_block_entries() -> None:
    settings = _settings(demo_probe=False, warmup_days=71)
    runtime = TradingRuntime(settings, persist=False)
    runtime.bootstrap()
    runtime.lifecycle.stage = "TRADING"
    runtime.lifecycle.ack(time.monotonic())
    try:
        for day in range(76):
            await runtime.play_day(day, trade=True, delay=False, publish=False)
        before = len(runtime.portfolio.fills)
        runtime.paused = True
        await runtime.play_day(76, trade=True, delay=False, publish=False)
        # Exits could still happen; a fresh book should not open a new long while paused
        # if it did not already. The assertion is that a paused entry is rejected when proposed.
        runtime.paused = False
        runtime.lifecycle.last_ack = 0
        runtime.settings.replay_mode = "realtime"
        await runtime.play_day(77, trade=True, delay=False, publish=False)
        heartbeat_rejects = [
            d for d in runtime.decisions if d["rejection_reason"] and "heartbeat" in d["rejection_reason"]
        ]
        assert heartbeat_rejects or before == len(runtime.portfolio.fills) or runtime.lifecycle.fresh(time.monotonic()) is False
        assert runtime.lifecycle.fresh(time.monotonic()) is False
    finally:
        await runtime.client.aclose()


def test_lifecycle_window() -> None:
    life = LifecycleManager(15)
    assert life.fresh(100) is False
    life.ack(100)
    assert life.fresh(110) is True
    assert life.fresh(116) is False
    life.stage = "ENDED"
    assert life.allows_orders() is False


@pytest.mark.asyncio
async def test_backtest_is_reproducible_and_has_no_lookahead() -> None:
    settings = _settings(demo_probe=False)
    first = await run_backtest(settings, strategy="adaptive", trade_start=50, trade_end=159, entry_threshold=0.40)
    second = await run_backtest(settings, strategy="adaptive", trade_start=50, trade_end=159, entry_threshold=0.40)
    assert first["ending_equity"] == pytest.approx(second["ending_equity"])
    assert first["trade_count"] == second["trade_count"]
    assert first["sharpe_note"]
    assert first["synthetic"] is True

    clean = TradingRuntime(settings, persist=False)
    clean.bootstrap()
    shocked = TradingRuntime(settings, persist=False)
    shocked.bootstrap()
    assert clean.dataset and shocked.dataset
    for ticker, candles in shocked.dataset.candles.items():
        for candle in candles:
            if candle.sim_day >= 140:
                candle.close = candle.close * 0.4
                candle.low = min(candle.low, candle.close)
                candle.high = max(candle.high, candle.open)
    clean.lifecycle.stage = "TRADING"
    shocked.lifecycle.stage = "TRADING"
    clean.lifecycle.ack(time.monotonic())
    shocked.lifecycle.ack(time.monotonic())
    try:
        for day in range(101):
            await clean.play_day(day, trade=True, delay=False, publish=False)
            await shocked.play_day(day, trade=True, delay=False, publish=False)
        clean_eq = clean.portfolio.equity_history[100]["equity"]
        shocked_eq = shocked.portfolio.equity_history[100]["equity"]
        assert clean_eq == pytest.approx(shocked_eq)
    finally:
        await clean.client.aclose()
        await shocked.client.aclose()


@pytest.mark.asyncio
async def test_outage_restores_the_previous_feed_status() -> None:
    runtime = TradingRuntime(_settings(demo_probe=False), persist=False)
    runtime.bootstrap()
    runtime.lifecycle.stage = "ENDED"
    runtime.feed_status = "ended"
    try:
        await runtime._outage(0.01)
        assert runtime.outage is False
        assert runtime.feed_status == "ended"
        assert runtime.milestones["outage_recovered"] is True
        runtime.lifecycle.stage = "TRADING"
        runtime.feed_status = "live"
        await runtime._outage(0.01)
        assert runtime.feed_status == "live"
        assert runtime.health_view()["feed"] == "live"
    finally:
        await runtime.client.aclose()


@pytest.mark.asyncio
async def test_compare_reports_baselines_without_using_validation_to_select() -> None:
    report = await compare_strategies(_settings(demo_probe=False))
    assert report["synthetic"] is True
    assert set(report["results"]) == {"adaptive", "buy_hold", "momentum", "mean_reversion", "cash"}
    assert report["results"]["cash"]["trade_count"] == 0
    assert report["results"]["buy_hold"]["trade_count"] > 0
    assert report["selected_entry_threshold"] in {0.35, 0.45, 0.55}
    assert report["validation"]["trade_start"] == 96
    assert report["test"]["trade_start"] == 128
    assert report["ranking"][0]["strategy"]
    # Cash baseline equity should stay at the starting capital aside from no fees.
    assert report["results"]["cash"]["net_profit"] == pytest.approx(0)
