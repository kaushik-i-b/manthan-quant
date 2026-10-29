"""Shared Pydantic models: internal events + venue payloads."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    SHORT = "SHORT"
    COVER = "COVER"
    HOLD = "HOLD"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class SimStage(str, Enum):
    PRE_FLIGHT = "PRE_FLIGHT"
    TRADING = "TRADING"
    PAUSED = "PAUSED"
    ENDED = "ENDED"


class Tick(BaseModel):
    ticker: str
    price: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    sim_day: int
    ts: datetime = Field(default_factory=utcnow)


class NewsEvent(BaseModel):
    ticker: str
    headline: str
    body: str = ""
    sentiment: str = "neutral"
    severity: float = 0.0
    sim_day: int = 0
    ts: datetime = Field(default_factory=utcnow)


class Signal(BaseModel):
    ticker: str
    action: Action
    score: float
    strategy: str
    indicators: dict[str, Any] = {}
    sentiment: Optional[str] = None
    regime: Optional[str] = None
    reason: str = ""
    risk_passed: Optional[bool] = None
    risk_reason: str = ""
    sim_day: int = 0
    ts: datetime = Field(default_factory=utcnow)


class OrderIntent(BaseModel):
    client_id: str
    ticker: str
    action: Action
    quantity: int
    ref_price: float
    sim_day: int = 0


class OrderResult(BaseModel):
    client_id: str
    ticker: str
    action: Action
    quantity: int
    status: OrderStatus
    fill_price: float = 0.0
    cost: float = 0.0
    reason: str = ""
    sim_day: int = 0
    ts: datetime = Field(default_factory=utcnow)


class Position(BaseModel):
    ticker: str
    qty: int = 0
    avg_price: float = 0.0
    short_qty: int = 0
    short_avg: float = 0.0


class PortfolioSnapshot(BaseModel):
    cash: float
    equity: float
    invested: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_return_pct: float = 0.0
    drawdown_pct: float = 0.0
    positions: dict[str, Position] = {}
    sim_day: int = 0
    ts: datetime = Field(default_factory=utcnow)
