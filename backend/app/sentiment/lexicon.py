"""Rule-based sentiment for headlines.

Scores are heuristic weights in [-1, 1], not calibrated probabilities.
"""

from __future__ import annotations

import math
import re

from app.models.types import NewsItem

POSITIVE = {
    "beat": 0.6,
    "growth": 0.5,
    "profit": 0.7,
    "record": 0.6,
    "upgrade": 0.8,
    "surge": 0.7,
    "expansion": 0.4,
    "dividend": 0.5,
    "buyback": 0.5,
    "wins": 0.4,
    "win": 0.4,
    "outperform": 0.6,
    "strong": 0.3,
    "approval": 0.5,
    "partnership": 0.3,
}
NEGATIVE = {
    "loss": 0.7,
    "losses": 0.7,
    "fraud": 0.95,
    "downgrade": 0.8,
    "decline": 0.5,
    "lawsuit": 0.7,
    "default": 0.9,
    "plunge": 0.8,
    "miss": 0.5,
    "investigation": 0.8,
    "warns": 0.6,
    "warning": 0.5,
    "volatile": 0.3,
    "sharp": 0.2,
    "penalty": 0.6,
    "resigns": 0.5,
    "bankruptcy": 1.0,
}
INTENSIFIERS = {"major": 0.25, "record": 0.15, "sharp": 0.2, "significant": 0.2, "massive": 0.25}

_TOKEN = re.compile(r"[a-zA-Z']+")


def score_text(text: str) -> tuple[float, float, str]:
    tokens = [tok.lower() for tok in _TOKEN.findall(text)]
    if not tokens:
        return 0.0, 0.0, "neutral"
    pos = sum(POSITIVE.get(tok, 0.0) for tok in tokens)
    neg = sum(NEGATIVE.get(tok, 0.0) for tok in tokens)
    raw = pos - neg
    sentiment = math.tanh(raw)
    intensity = sum(INTENSIFIERS.get(tok, 0.0) for tok in tokens)
    magnitude = min(1.0, abs(raw) / 1.4)
    severity = min(1.0, magnitude + intensity)
    if sentiment > 0.2:
        label = "positive"
    elif sentiment < -0.2:
        label = "negative"
    else:
        label = "neutral"
    return sentiment, severity, label


def annotate(item: NewsItem, current_day: int | None = None) -> NewsItem:
    sentiment, severity, label = score_text(f"{item.headline} {item.body}")
    if current_day is not None:
        age = max(0, current_day - item.sim_day)
        freshness = math.exp(-age / 2.0)
        severity = severity * freshness
        sentiment = sentiment * freshness
    return item.model_copy(update={"sentiment": sentiment, "severity": severity, "label": label})
