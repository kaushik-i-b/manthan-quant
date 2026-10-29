"""Backtests reuse the live decision, risk, and accounting code.

Indicators are updated one simulated day at a time. The strategy never
receives a later candle. Train days pick an entry threshold; validation is
reported and not used for selection; the test window is reported separately.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from app.config import Settings
from app.runtime import TradingRuntime

SHARPE_NOTE = (
    "Scaled by sqrt(252), treating each simulated bar as one trading day. "
    "Risk-free rate is 0. This is a relative score on this tape, not a calendar Sharpe."
)


def _rank_key(row: dict) -> tuple:
    sharpe = row["sharpe"]
    return (
        sharpe is not None,
        sharpe if sharpe is not None else -1e9,
        -row["turnover"],
        row["total_return_pct"],
    )


def summarize(runtime: TradingRuntime, *, trade_start: int, trade_end: int, elapsed_ms: float) -> dict:
    history = [row for row in runtime.portfolio.equity_history if trade_start <= row["sim_day"] <= trade_end]
    if not history:
        history = list(runtime.portfolio.equity_history)
    frame = pd.DataFrame(history)
    if frame.empty:
        returns = pd.Series(dtype=float)
    else:
        returns = frame["equity"].pct_change().dropna()
    sharpe = None
    if len(returns) >= 2 and float(returns.std(ddof=0)) > 0:
        sharpe = float(returns.mean() / returns.std(ddof=0) * np.sqrt(252))
    start_equity = float(history[0]["equity"]) if history else runtime.portfolio.starting_capital
    end_equity = float(history[-1]["equity"]) if history else start_equity
    peak = start_equity
    max_dd = 0.0
    curve = []
    for row in history:
        equity = float(row["equity"])
        peak = max(peak, equity)
        dd = 0.0 if peak <= 0 else (peak - equity) / peak
        max_dd = max(max_dd, dd)
        curve.append({"sim_day": int(row["sim_day"]), "equity": equity, "drawdown": dd})
    gross_wins = sum(trade.net_pnl for trade in runtime.portfolio.closed if trade.net_pnl > 0)
    gross_losses = sum(-trade.net_pnl for trade in runtime.portfolio.closed if trade.net_pnl < 0)
    profit_factor = None if gross_losses <= 0 else gross_wins / gross_losses
    notional = sum(fill.quantity * fill.price for fill in runtime.portfolio.fills)
    mean_equity = float(frame["equity"].mean()) if not frame.empty else start_equity
    turnover = 0.0 if mean_equity <= 0 else notional / mean_equity
    avg_exposure = float(frame["gross_exposure"].mean()) if not frame.empty and "gross_exposure" in frame else 0.0
    avg_cash = float(frame["cash"].mean()) if not frame.empty else 0.0
    net_profit = end_equity - runtime.portfolio.starting_capital
    closed = runtime.portfolio.closed
    wins = sum(1 for trade in closed if trade.net_pnl > 0)
    return {
        "strategy": runtime.strategy_mode,
        "entry_threshold": runtime.settings.entry_threshold,
        "trade_start": trade_start,
        "trade_end": trade_end,
        "total_return_pct": 0.0 if runtime.portfolio.starting_capital == 0 else net_profit / runtime.portfolio.starting_capital * 100,
        "net_profit": net_profit,
        "ending_equity": end_equity,
        "max_drawdown_pct": max_dd * 100,
        "sharpe": sharpe,
        "sharpe_note": SHARPE_NOTE,
        "win_rate": None if not closed else wins / len(closed),
        "profit_factor": profit_factor,
        "trade_count": len(runtime.portfolio.fills),
        "closed_trades": len(closed),
        "turnover": turnover,
        "transaction_costs": runtime.portfolio.fees_paid,
        "avg_cash": avg_cash,
        "avg_exposure": avg_exposure,
        "rejected_orders": runtime.rejected_count,
        "decision_latency_ms_p50": runtime.latency.p50,
        "elapsed_ms": elapsed_ms,
        "equity": curve,
        "synthetic": True,
    }


async def run_backtest(
    settings: Settings,
    *,
    strategy: str,
    trade_start: int,
    trade_end: int,
    entry_threshold: float | None = None,
) -> dict:
    local = settings.model_copy(deep=True)
    local.replay_mode = "instant"
    local.market_mode = "mock"
    local.demo_probe = False
    if entry_threshold is not None:
        local.entry_threshold = entry_threshold
    runtime = TradingRuntime(local, persist=False)
    runtime.strategy_mode = strategy
    runtime.bootstrap()
    runtime.lifecycle.stage = "TRADING"
    runtime.lifecycle.ack(time.monotonic())
    started = time.perf_counter()
    try:
        assert runtime.dataset is not None
        last = min(trade_end, runtime.dataset.days - 1)
        for day in range(last + 1):
            await runtime.play_day(day, trade=trade_start <= day <= trade_end, delay=False, publish=False)
        elapsed = (time.perf_counter() - started) * 1000
        return summarize(runtime, trade_start=trade_start, trade_end=trade_end, elapsed_ms=elapsed)
    finally:
        await runtime.client.aclose()


async def compare_strategies(settings: Settings) -> dict:
    started = time.perf_counter()
    grid = [0.35, 0.45, 0.55]
    train_rows = []
    for threshold in grid:
        train_rows.append(
            await run_backtest(
                settings,
                strategy="adaptive",
                trade_start=50,
                trade_end=95,
                entry_threshold=threshold,
            )
        )
    chosen = max(train_rows, key=_rank_key)
    threshold = chosen["entry_threshold"]
    validation = await run_backtest(
        settings, strategy="adaptive", trade_start=96, trade_end=127, entry_threshold=threshold
    )
    test = await run_backtest(
        settings, strategy="adaptive", trade_start=128, trade_end=159, entry_threshold=threshold
    )
    full: dict[str, dict] = {}
    for name in ("adaptive", "buy_hold", "momentum", "mean_reversion", "cash"):
        full[name] = await run_backtest(
            settings,
            strategy=name,
            trade_start=50,
            trade_end=159,
            entry_threshold=threshold if name == "adaptive" else settings.entry_threshold,
        )
        full[name]["equity"] = full[name]["equity"]
    ranking = sorted(
        ({"strategy": name, **{k: v for k, v in row.items() if k != "equity"}} for name, row in full.items()),
        key=_rank_key,
        reverse=True,
    )
    elapsed = (time.perf_counter() - started) * 1000
    return {
        "dataset": "synthetic_demo_v1",
        "synthetic": True,
        "disclaimer": "Synthetic tape only. These numbers are not competition performance.",
        "seed": settings.synthetic_seed,
        "elapsed_ms": elapsed,
        "splits": {"train": [50, 95], "validation": [96, 127], "test": [128, 159]},
        "selection_rule": "Highest train Sharpe. Ties prefer lower turnover, then higher total return. Validation is not used to pick the threshold.",
        "selected_entry_threshold": threshold,
        "train": [{k: v for k, v in row.items() if k != "equity"} for row in train_rows],
        "validation": {k: v for k, v in validation.items() if k != "equity"},
        "test": {k: v for k, v in test.items() if k != "equity"},
        "ranking": ranking,
        "results": full,
    }
