"""Backtesting: chronological replay, no lookahead, standard metrics."""
from __future__ import annotations

import math

from app.indicators.engine import IndicatorEngine
from app.models.schemas import Action
from app.portfolio.manager import Portfolio
from app.risk.engine import RiskEngine
from app.strategies import engine as strat


def run_backtest(candles_by_symbol: dict[str, list[dict]], strategy: str = "adaptive",
                 starting: float = 1_000_000.0) -> dict:
    ind = IndicatorEngine()
    pf = Portfolio(starting)
    risk = RiskEngine()
    sim_day = 0
    # chronological interleave by index
    maxlen = max(len(v) for v in candles_by_symbol.values())
    symbols = list(candles_by_symbol.keys())
    for i in range(maxlen):
        sim_day += 1
        prices = {}
        for s in symbols:
            bars = candles_by_symbol[s]
            if i >= len(bars):
                continue
            b = bars[i]
            prices[s] = b["close"]
            snap = ind.on_candle(s, b["open"], b["high"], b["low"], b["close"], b["volume"])
            ctx = strat.Ctx(ticker=s, ind=snap, sim_day=sim_day)
            if strategy == "trend":
                sig = strat.trend_strategy(ctx)
            elif strategy == "meanrev":
                sig = strat.mean_reversion_strategy(ctx)
            elif strategy == "breakout":
                hi = max(x["high"] for x in bars[max(0, i - 20):i]) if i > 0 else None
                lo = min(x["low"] for x in bars[max(0, i - 20):i]) if i > 0 else None
                sig = strat.breakout_strategy(ctx, hi, lo)
            else:
                votes = [strat.trend_strategy(ctx), strat.mean_reversion_strategy(ctx)]
                hi = max(x["high"] for x in bars[max(0, i - 20):i]) if i > 0 else None
                lo = min(x["low"] for x in bars[max(0, i - 20):i]) if i > 0 else None
                votes.append(strat.breakout_strategy(ctx, hi, lo))
                regime = strat.classify_regime(snap, False, "neutral")
                sig = strat.combine(votes, regime)
            if sig.action != Action.HOLD:
                eq = pf.equity(prices)
                d = risk.evaluate(sig, pf.cash, eq, pf.positions, b["close"], 0.0, 0, True, False, True)
                if d.passed:
                    pf.apply_fill(s, sig.action if sig.action in (Action.BUY, Action.SELL) else Action.BUY
                                 if sig.action == Action.BUY else Action.SELL, d.quantity, b["close"])
        pf.snapshot(prices, sim_day)
    eq_hist = [e["equity"] for e in pf.equity_hist]
    rets = [(eq_hist[i] - eq_hist[i - 1]) / eq_hist[i - 1] for i in range(1, len(eq_hist)) if eq_hist[i - 1]]
    peak = eq_hist[0] if eq_hist else starting
    maxdd = 0.0
    for e in eq_hist:
        peak = max(peak, e)
        maxdd = max(maxdd, (peak - e) / peak if peak else 0)
    mean = sum(rets) / len(rets) if rets else 0
    sd = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5 if len(rets) > 1 else 0
    sharpe = (mean / sd * math.sqrt(252)) if sd else 0.0
    return {
        "strategy": strategy,
        "starting": starting,
        "final_equity": round(eq_hist[-1], 2) if eq_hist else starting,
        "total_return_pct": round((eq_hist[-1] - starting) / starting * 100, 3) if eq_hist else 0,
        "max_drawdown_pct": round(maxdd * 100, 3),
        "sharpe": round(sharpe, 3),
        "trades": pf.trade_count,
        "win_rate_pct": round(pf.wins / pf.trade_count * 100, 1) if pf.trade_count else 0,
        "fees": round(pf.fees_paid, 2),
        "equity_curve": pf.equity_hist,
        "realized_pnl": round(pf.realized, 2),
    }
