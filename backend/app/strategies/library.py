"""Strategy A–E.

Scores are heuristic and bounded to [-1, 1]. They are not probabilities.
"""

from __future__ import annotations

from app.models.types import IndicatorSnapshot, NewsItem, StrategyView


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def trend_following(snap: IndicatorSnapshot) -> StrategyView:
    if not snap.ready or snap.ema9 is None or snap.ema21 is None:
        return StrategyView(name="trend", score=0.0, reasons=["trend waiting for indicator warmup"])
    score = 0.0
    reasons: list[str] = []
    if snap.ema9 > snap.ema21:
        score += 0.35
        reasons.append("EMA9 is above EMA21")
    elif snap.ema9 < snap.ema21:
        score -= 0.35
        reasons.append("EMA9 is below EMA21")
    if snap.ema50 is not None and snap.ema21 > snap.ema50:
        score += 0.25
        reasons.append("EMA21 is above EMA50")
    elif snap.ema50 is not None and snap.ema21 < snap.ema50:
        score -= 0.25
        reasons.append("EMA21 is below EMA50")
    if snap.momentum10 is not None and snap.momentum10 > 0:
        score += 0.20
        reasons.append("10-bar momentum is positive")
    elif snap.momentum10 is not None and snap.momentum10 < 0:
        score -= 0.20
        reasons.append("10-bar momentum is negative")
    if snap.volatility20 is not None and snap.volatility20 > 0.03:
        score *= 0.35
        reasons.append("volatility filter dampened the trend score")
    if snap.rsi14 is not None and (snap.rsi14 > 80 or snap.rsi14 < 20):
        score *= 0.5
        reasons.append("RSI is extended, so the trend score was dampened")
    return StrategyView(name="trend", score=_clamp(score), reasons=reasons)


def mean_reversion(snap: IndicatorSnapshot) -> StrategyView:
    if not snap.ready or snap.close is None:
        return StrategyView(name="mean_reversion", score=0.0, reasons=["mean reversion waiting for warmup"])
    score = 0.0
    reasons: list[str] = []
    if snap.rsi14 is not None and snap.rsi14 <= 30:
        score += 0.45
        reasons.append(f"RSI {snap.rsi14:.1f} is oversold")
    elif snap.rsi14 is not None and snap.rsi14 >= 70:
        score -= 0.45
        reasons.append(f"RSI {snap.rsi14:.1f} is overbought")
    if snap.bb_lower is not None and snap.close < snap.bb_lower:
        score += 0.35
        reasons.append("close is below the lower Bollinger band")
    if snap.bb_upper is not None and snap.close > snap.bb_upper:
        score -= 0.35
        reasons.append("close is above the upper Bollinger band")
    if snap.sma20 is not None and snap.close < snap.sma20:
        score += 0.10
        reasons.append("close is below SMA20")
    elif snap.sma20 is not None and snap.close > snap.sma20:
        score -= 0.10
        reasons.append("close is above SMA20")
    if snap.volume_ratio20 is not None and snap.volume_ratio20 >= 1.2 and score != 0:
        score *= 1.1
        reasons.append("volume confirms the reversion setup")
    return StrategyView(name="mean_reversion", score=_clamp(score), reasons=reasons)


def momentum_breakout(snap: IndicatorSnapshot) -> StrategyView:
    if not snap.ready or snap.close is None:
        return StrategyView(name="breakout", score=0.0, reasons=["breakout waiting for warmup"])
    score = 0.0
    reasons: list[str] = []
    volume_ok = snap.volume_ratio20 is not None and snap.volume_ratio20 >= 1.8
    if snap.prior_high20 is not None and snap.close > snap.prior_high20 and (snap.roc10 or 0) > 0:
        score += 0.55 if volume_ok else 0.25
        reasons.append("close broke the prior 20-bar high")
        if volume_ok:
            reasons.append("volume is elevated versus the prior 20-bar average")
    if snap.prior_low20 is not None and snap.close < snap.prior_low20 and (snap.roc10 or 0) < 0:
        score -= 0.55 if volume_ok else 0.25
        reasons.append("close broke the prior 20-bar low")
        if volume_ok:
            reasons.append("volume confirms the downside break")
    if snap.momentum10 is not None and abs(snap.momentum10) > 0.02:
        score += 0.15 if snap.momentum10 > 0 else -0.15
        reasons.append("price acceleration is outside the 2% band")
    return StrategyView(name="breakout", score=_clamp(score), reasons=reasons or ["no breakout"])


def news_driven(news: NewsItem | None) -> StrategyView:
    if news is None or news.sentiment is None or news.severity is None:
        return StrategyView(name="news", score=0.0, reasons=["no fresh news"])
    score = _clamp(news.sentiment * max(news.severity, 0.0))
    reasons = [
        news.headline,
        f"local lexicon label {news.label}, sentiment {news.sentiment:.2f}, severity {news.severity:.2f}",
    ]
    return StrategyView(name="news", score=score, reasons=reasons)


def defensive(data_ok: bool, drawdown: float, max_drawdown: float, volatility: float | None) -> StrategyView:
    reasons: list[str] = []
    force = False
    if not data_ok:
        force = True
        reasons.append("market data failed the freshness check")
    if drawdown >= max_drawdown * 0.85:
        force = True
        reasons.append("portfolio drawdown is near the hard limit")
    if volatility is not None and volatility > 0.05:
        force = True
        reasons.append("cross-sectional volatility is extreme")
    if not reasons:
        reasons.append("defensive overlay is idle")
    return StrategyView(name="defensive", score=0.0, reasons=reasons, force_flat=force)
