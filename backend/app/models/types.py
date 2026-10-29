"""Internal event and order models.

These are MANTHAN QUANT models. They are not a claim about the competition
Kafka or REST schemas. Venue bytes are decoded only through an explicit field map.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["BUY", "SELL", "SHORT", "COVER", "HOLD"]
OrderStatus = Literal[
    "PENDING",
    "FILLED",
    "REJECTED",
    "FAILED",
    "UNKNOWN",
    "BLOCKED",
]


class Candle(BaseModel):
    event_id: str
    ticker: str
    sim_day: int
    ts_unix: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str = "synthetic"
    schema_name: str = "manthan-quant.internal.tick.v1"


class NewsItem(BaseModel):
    event_id: str
    ticker: str
    sim_day: int
    ts_unix: int
    headline: str
    body: str
    source: str = "synthetic"
    schema_name: str = "manthan-quant.internal.news.v1"
    sentiment: float | None = None
    severity: float | None = None
    label: str | None = None


class IndicatorSnapshot(BaseModel):
    ready: bool = False
    close: float | None = None
    ema9: float | None = None
    ema21: float | None = None
    ema50: float | None = None
    sma20: float | None = None
    sma50: float | None = None
    rsi14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    atr14: float | None = None
    bb_mid: float | None = None
    bb_upper: float | None = None
    bb_lower: float | None = None
    bb_width: float | None = None
    volatility20: float | None = None
    momentum10: float | None = None
    roc10: float | None = None
    volume_ratio20: float | None = None
    trend_strength: float | None = None
    prior_high20: float | None = None
    prior_low20: float | None = None
    price_drawdown: float | None = None


class StrategyView(BaseModel):
    name: str
    score: float
    reasons: list[str] = Field(default_factory=list)
    force_flat: bool = False


class OrderIntent(BaseModel):
    client_order_id: str
    ticker: str
    action: Literal["BUY", "SELL", "SHORT", "COVER"]
    quantity: int
    price: float
    sim_day: int
    strategy: str
    reason: str
    signal_score: float
    is_exit: bool = False
    score_type: str = "heuristic"


class RiskResult(BaseModel):
    approved: bool
    reasons: list[str]


class Fill(BaseModel):
    client_order_id: str
    order_id: str
    ticker: str
    action: Literal["BUY", "SELL", "SHORT", "COVER"]
    quantity: int
    price: float
    sim_day: int
    status: OrderStatus
    brokerage: float = 0.0
    taxes_and_fees: float = 0.0
    message: str = ""
    venue: str = "mock"
    strategy: str = ""
    signal_score: float = 0.0
    reason: str = ""
