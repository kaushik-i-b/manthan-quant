"""Fast local rule-based news sentiment classifier (no remote calls in trading path)."""
from __future__ import annotations

import re

POS = ["profit", "growth", "surge", "record", "beat", "upgrade", "bullish", "gain", "soar",
       "expansion", "dividend", "buyback", "outperform", "strong", "breakthrough", "deal", "wins", "approval"]
NEG = ["loss", "fall", "plunge", "miss", "downgrade", "bearish", "fraud", "probe", "scam",
       "penalty", "fine", "lawsuit", "default", "cut", "warning", "recall", "weak", "decline", "crash"]


def classify(headline: str, body: str = "") -> tuple[str, float]:
    text = f"{headline} {body}".lower()
    pos = sum(1 for w in POS if w in text)
    neg = sum(1 for w in NEG if w in text)
    # severity: exclamation, caps ratio, negative keywords density
    sev = min(1.0, (abs(pos - neg) * 0.25) + (0.2 if "!" in headline else 0.0))
    if pos > neg:
        return "positive", min(1.0, 0.4 + 0.15 * (pos - neg))
    if neg > pos:
        return "negative", min(1.0, 0.4 + 0.15 * (neg - pos))
    return "neutral", 0.0


def extract_ticker(headline: str, body: str, known: list[str]) -> str | None:
    text = f"{headline} {body}".upper()
    for t in known:
        if re.search(rf"\b{re.escape(t)}\b", text):
            return t
    return None
