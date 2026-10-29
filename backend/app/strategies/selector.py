"""Regime weights. The displayed score is a weighted heuristic, not a probability."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.types import IndicatorSnapshot, NewsItem
from app.strategies.library import (
    defensive,
    mean_reversion,
    momentum_breakout,
    news_driven,
    trend_following,
)

WEIGHTS: dict[str, dict[str, float]] = {
    "trending_bullish": {"trend": 0.50, "breakout": 0.22, "mean_reversion": 0.05, "news": 0.15, "defensive": 0.08},
    "trending_bearish": {"trend": 0.48, "breakout": 0.20, "mean_reversion": 0.05, "news": 0.17, "defensive": 0.10},
    "sideways": {"trend": 0.10, "breakout": 0.12, "mean_reversion": 0.48, "news": 0.20, "defensive": 0.10},
    "high_volatility": {"trend": 0.12, "breakout": 0.10, "mean_reversion": 0.13, "news": 0.15, "defensive": 0.50},
    "low_volatility": {"trend": 0.30, "breakout": 0.22, "mean_reversion": 0.28, "news": 0.12, "defensive": 0.08},
    "news_driven": {"trend": 0.12, "breakout": 0.10, "mean_reversion": 0.08, "news": 0.55, "defensive": 0.15},
    "unreliable": {"trend": 0.0, "breakout": 0.0, "mean_reversion": 0.0, "news": 0.0, "defensive": 1.0},
}


def classify_regime(snap: IndicatorSnapshot, news: NewsItem | None, data_ok: bool) -> str:
    if not data_ok or not snap.ready:
        return "unreliable" if not data_ok else "low_volatility"
    if news and news.severity is not None and news.severity >= 0.55 and news.sentiment is not None:
        if abs(news.sentiment) >= 0.35:
            return "news_driven"
    vol = snap.volatility20
    if vol is not None and vol >= 0.03:
        return "high_volatility"
    bullish = (
        snap.ema9 is not None
        and snap.ema21 is not None
        and snap.ema50 is not None
        and snap.ema9 > snap.ema21 > snap.ema50
    )
    bearish = (
        snap.ema9 is not None
        and snap.ema21 is not None
        and snap.ema50 is not None
        and snap.ema9 < snap.ema21 < snap.ema50
    )
    if bullish and (snap.trend_strength or 0) >= 0.6:
        return "trending_bullish"
    if bearish and (snap.trend_strength or 0) >= 0.6:
        return "trending_bearish"
    if vol is not None and vol < 0.008:
        return "low_volatility"
    return "sideways"


@dataclass
class Selection:
    action_bias: float
    regime: str
    primary: str
    views: list
    contributions: dict
    force_flat: bool
    reason: str


class StrategySelector:
    def select(
        self,
        snap: IndicatorSnapshot,
        news: NewsItem | None,
        *,
        data_ok: bool,
        drawdown: float,
        max_drawdown: float,
    ) -> Selection:
        regime = classify_regime(snap, news, data_ok)
        views = [
            trend_following(snap),
            mean_reversion(snap),
            momentum_breakout(snap),
            news_driven(news),
            defensive(data_ok, drawdown, max_drawdown, snap.volatility20),
        ]
        weights = WEIGHTS[regime]
        contributions = {}
        combined = 0.0
        for view in views:
            weight = weights.get(view.name, 0.0)
            weighted = weight * view.score
            contributions[view.name] = {
                "score": round(view.score, 4),
                "weight": weight,
                "weighted": round(weighted, 4),
                "reasons": view.reasons,
            }
            combined += weighted
        force = any(view.force_flat for view in views) or regime == "unreliable"
        ranked = sorted(contributions.items(), key=lambda item: abs(item[1]["weighted"]), reverse=True)
        primary = ranked[0][0] if ranked else "defensive"
        if force:
            primary = "defensive"
        bits = []
        for view in views:
            if view.reasons:
                bits.append(f"{view.name}: {view.reasons[0]}")
        reason = f"Regime {regime}. " + " ".join(bits)
        return Selection(
            action_bias=max(-1.0, min(1.0, combined)),
            regime=regime,
            primary=primary,
            views=views,
            contributions=contributions,
            force_flat=force,
            reason=reason,
        )
