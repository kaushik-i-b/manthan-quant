"""Deterministic baseline strategies + adaptive regime selector."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import Action, Signal


@dataclass
class Ctx:
    ticker: str
    ind: dict
    sentiment: str = "neutral"
    severity: float = 0.0
    news_fresh: bool = False
    sim_day: int = 0


def _sig(ticker, action, score, strategy, ind, reason, sentiment=None, regime=None, sim_day=0) -> Signal:
    return Signal(ticker=ticker, action=action, score=max(0.0, min(1.0, score)),
                  strategy=strategy, indicators={k: (round(v, 4) if isinstance(v, float) else v) for k, v in ind.items() if v is not None},
                  sentiment=sentiment, regime=regime, reason=reason, sim_day=sim_day)


def trend_strategy(c: Ctx) -> Signal:
    i = c.ind
    if (c.ind.get("bars") or 0) < 55:
        return _sig(c.ticker, Action.HOLD, 0.5, "trend", i, "Insufficient history (<55 bars)", sim_day=c.sim_day)
    bull = (i.get("ema9") or 0) > (i.get("ema21") or 0) > (i.get("ema50") or 0)
    bear = (i.get("ema9") or 0) < (i.get("ema21") or 0) < (i.get("ema50") or 0)
    mom = i.get("momentum") or 0
    vol = i.get("volatility") or 0
    if vol > 0.08:
        return _sig(c.ticker, Action.HOLD, 0.45, "trend", i, f"Volatility filter blocked (vol={vol:.3f})", sim_day=c.sim_day)
    if bull and mom > 0:
        return _sig(c.ticker, Action.BUY, 0.72, "trend", i, "EMA9>EMA21>EMA50 with positive momentum", sim_day=c.sim_day)
    if bear and mom < 0:
        return _sig(c.ticker, Action.SELL, 0.70, "trend", i, "EMA9<EMA21<EMA50 with negative momentum", sim_day=c.sim_day)
    return _sig(c.ticker, Action.HOLD, 0.5, "trend", i, "No EMA alignment", sim_day=c.sim_day)


def mean_reversion_strategy(c: Ctx) -> Signal:
    i = c.ind
    if (i.get("bars") or 0) < 25:
        return _sig(c.ticker, Action.HOLD, 0.5, "meanrev", i, "Insufficient history", sim_day=c.sim_day)
    rsi = i.get("rsi14")
    px, lo, hi = i.get("price"), i.get("bb_lower"), i.get("bb_upper")
    va = i.get("volume_anomaly") or 0
    if rsi is None or px is None:
        return _sig(c.ticker, Action.HOLD, 0.5, "meanrev", i, "Indicators warming up", sim_day=c.sim_day)
    if rsi < 30 and lo is not None and px <= lo * 1.01:
        return _sig(c.ticker, Action.BUY, 0.68, "meanrev", i, f"Oversold bounce: RSI={rsi:.1f}, price at lower band", sim_day=c.sim_day)
    if rsi > 70 and hi is not None and px >= hi * 0.99:
        return _sig(c.ticker, Action.SELL, 0.68, "meanrev", i, f"Overbought fade: RSI={rsi:.1f}, price at upper band", sim_day=c.sim_day)
    if rsi < 35 and va and va > 1.5:
        return _sig(c.ticker, Action.BUY, 0.60, "meanrev", i, f"RSI {rsi:.1f} with volume confirmation x{va:.1f}", sim_day=c.sim_day)
    return _sig(c.ticker, Action.HOLD, 0.5, "meanrev", i, f"RSI={rsi:.1f} no extreme", sim_day=c.sim_day)


def breakout_strategy(c: Ctx, recent_high: float | None, recent_low: float | None) -> Signal:
    i = c.ind
    px = i.get("price")
    if px is None or recent_high is None or (i.get("bars") or 0) < 25:
        return _sig(c.ticker, Action.HOLD, 0.5, "breakout", i, "Warming up", sim_day=c.sim_day)
    atr = i.get("atr14") or px * 0.01
    va = i.get("volume_anomaly") or 1.0
    thresh = recent_high + 0.25 * atr
    if px >= thresh and va > 1.4:
        return _sig(c.ticker, Action.BUY, 0.75, "breakout", i, f"Breakout above {recent_high:.2f} with volume x{va:.1f}", sim_day=c.sim_day)
    if recent_low and px <= recent_low - 0.25 * atr and va > 1.4:
        return _sig(c.ticker, Action.SELL, 0.72, "breakout", i, "Breakdown with volume", sim_day=c.sim_day)
    return _sig(c.ticker, Action.HOLD, 0.5, "breakout", i, "Inside range", sim_day=c.sim_day)


def news_strategy(c: Ctx) -> Signal:
    if not c.news_fresh:
        return _sig(c.ticker, Action.HOLD, 0.5, "news", c.ind, "No fresh news", sentiment=c.sentiment, sim_day=c.sim_day)
    if c.sentiment == "positive" and c.severity >= 0.4:
        return _sig(c.ticker, Action.BUY, min(0.85, 0.55 + c.severity * 0.3), "news", c.ind,
                    f"Positive news severity={c.severity:.2f}", sentiment=c.sentiment, sim_day=c.sim_day)
    if c.sentiment == "negative" and c.severity >= 0.4:
        return _sig(c.ticker, Action.SELL, min(0.85, 0.55 + c.severity * 0.3), "news", c.ind,
                    f"Negative news severity={c.severity:.2f}", sentiment=c.sentiment, sim_day=c.sim_day)
    return _sig(c.ticker, Action.HOLD, 0.5, "news", c.ind, "Neutral/weak news", sentiment=c.sentiment, sim_day=c.sim_day)


def defensive_vote(portfolio_drawdown: float, market_vol: float, max_dd: float = 0.08) -> Signal | None:
    if portfolio_drawdown >= max_dd or market_vol > 0.09:
        return Signal(ticker="*", action=Action.HOLD, score=0.2, strategy="defensive",
                      reason=f"Defensive: dd={portfolio_drawdown:.3f} vol={market_vol:.3f}")
    return None


def classify_regime(ind: dict, news_fresh: bool, sentiment: str) -> str:
    t = ind.get("trend_strength") or 0
    vol = ind.get("volatility") or 0
    if news_fresh and sentiment in ("positive", "negative"):
        return "news-driven"
    if vol > 0.07:
        return "high-volatility"
    if t >= 1.0:
        return "trending-bullish"
    if t <= -1.0:
        return "trending-bearish"
    if vol < 0.02:
        return "low-volatility"
    return "sideways"


STRATEGY_WEIGHTS = {
    "trending-bullish": {"trend": 0.5, "breakout": 0.3, "meanrev": 0.1, "news": 0.1},
    "trending-bearish": {"trend": 0.5, "breakout": 0.2, "meanrev": 0.2, "news": 0.1},
    "sideways": {"meanrev": 0.5, "trend": 0.2, "breakout": 0.2, "news": 0.1},
    "high-volatility": {"defensive": 1.0},
    "low-volatility": {"breakout": 0.4, "trend": 0.3, "meanrev": 0.3, "news": 0.0},
    "news-driven": {"news": 0.6, "trend": 0.2, "breakout": 0.2, "meanrev": 0.0},
}


def combine(signals: list[Signal], regime: str) -> Signal:
    """Weighted vote across strategies. HOLD unless directional score clears 0.60."""
    weights = STRATEGY_WEIGHTS.get(regime, {"trend": 0.4, "meanrev": 0.3, "breakout": 0.3})
    buy = sum(s.score * weights.get(s.strategy, 0.1) for s in signals if s.action == Action.BUY)
    sell = sum(s.score * weights.get(s.strategy, 0.1) for s in signals if s.action in (Action.SELL,))
    best = max(signals, key=lambda s: s.score, default=None)
    ticker = best.ticker if best else "?"
    sim_day = best.sim_day if best else 0
    contribs = {s.strategy: round(s.score, 3) for s in signals}
    base_ind = dict(best.indicators) if best else {}
    base_ind["contributions"] = contribs
    if buy >= 0.60 and buy > sell:
        s = _sig(ticker, Action.BUY, min(0.95, buy + 0.2), "adaptive", base_ind,
                 f"Regime={regime} weighted buy={buy:.2f}", regime=regime, sim_day=sim_day)
    elif sell >= 0.60 and sell > buy:
        s = _sig(ticker, Action.SELL, min(0.95, sell + 0.2), "adaptive", base_ind,
                 f"Regime={regime} weighted sell={sell:.2f}", regime=regime, sim_day=sim_day)
    else:
        s = _sig(ticker, Action.HOLD, 0.5, "adaptive", base_ind,
                 f"Regime={regime} no consensus (buy={buy:.2f} sell={sell:.2f})", regime=regime, sim_day=sim_day)
    return s
