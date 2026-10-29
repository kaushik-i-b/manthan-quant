"""Pre-trade risk gate.

A failed check returns reasons and must stop the execution pipeline.
Exits are still checked, but drawdown and defensive pauses do not block
risk-reducing exits. Entries are blocked.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import Settings
from app.execution.costs import quote_cost
from app.models.types import OrderIntent, RiskResult
from app.portfolio.accounting import Portfolio


@dataclass
class RiskContext:
    stage: str
    heartbeat_fresh: bool
    paused: bool
    data_stale: bool
    portfolio_reliable: bool
    rate_limit_ok: bool
    live_armed: bool
    market_mode: str
    marks: dict[str, float]
    orders_today: int
    outstanding: int
    seen_order_ids: set[str] = field(default_factory=set)
    auth_ok: bool = True


def size_entry(settings: Settings, equity: float, price: float, atr: float | None, score: float) -> int:
    if price <= 0 or equity <= 0 or score == 0:
        return 0
    conviction = min(1.0, abs(score))
    cap_notional = equity * settings.max_position_pct * conviction
    cap_qty = int(cap_notional // price)
    if atr and atr > 0:
        risk_budget = equity * settings.risk_per_trade_pct * conviction
        vol_qty = int(risk_budget // atr)
        qty = min(cap_qty, vol_qty)
    else:
        qty = cap_qty
    return max(qty, 0)


class RiskEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(self, intent: OrderIntent, portfolio: Portfolio, ctx: RiskContext) -> RiskResult:
        reasons: list[str] = []
        settings = self.settings

        if ctx.stage != "TRADING":
            reasons.append(f"simulation stage is {ctx.stage}; orders are blocked outside TRADING")
        if not ctx.heartbeat_fresh:
            reasons.append("heartbeat acknowledgement is missing or older than 15 seconds")
        if ctx.data_stale:
            reasons.append("market data is stale")
        if not ctx.portfolio_reliable:
            reasons.append("portfolio state is unreliable")
        if not ctx.rate_limit_ok:
            reasons.append("API rate limit budget is exhausted")
        if ctx.market_mode == "venue" and not ctx.auth_ok:
            reasons.append("venue authentication is not configured")
        if ctx.market_mode == "venue" and not ctx.live_armed:
            reasons.append("live submission is not armed (DRY_RUN, TRADING_ENABLED, or confirmation)")
        if intent.client_order_id in ctx.seen_order_ids:
            reasons.append("duplicate client order id")
        if ctx.outstanding >= settings.max_outstanding_orders:
            reasons.append("maximum outstanding orders reached")
        if not intent.is_exit and ctx.orders_today >= settings.max_orders_per_day:
            reasons.append("maximum new orders for this simulated day reached")
        if intent.ticker in portfolio.frozen:
            reasons.append("ticker is frozen after an unknown submission")
        if intent.quantity < 1 or int(intent.quantity) != intent.quantity:
            reasons.append("quantity must be a positive integer")
        if intent.price <= 0:
            reasons.append("price must be positive")

        pos = portfolio.position(intent.ticker)
        if intent.action == "BUY" and pos and pos.side != "long":
            reasons.append("BUY is blocked while a short is open; COVER first")
        if intent.action == "SHORT" and pos and pos.side != "short":
            reasons.append("SHORT is blocked while a long is open; SELL first")
        if intent.action == "SELL" and (pos is None or pos.side != "long" or intent.quantity > pos.quantity):
            reasons.append("SELL quantity exceeds the long position")
        if intent.action == "COVER" and (pos is None or pos.side != "short" or intent.quantity > pos.quantity):
            reasons.append("COVER quantity exceeds the short position")
        if intent.action == "SHORT" and not settings.shorts_enabled:
            reasons.append("short selling is disabled")
        if ctx.paused and not intent.is_exit:
            reasons.append("trading is paused")

        marks = dict(ctx.marks)
        marks.setdefault(intent.ticker, intent.price)
        equity = portfolio.equity(marks)
        if equity <= 0:
            reasons.append("equity is not positive")

        turnover = intent.quantity * intent.price
        cost = quote_cost(settings, turnover)
        fee = cost.total

        if intent.action in {"BUY", "SHORT"} and not intent.is_exit:
            dd = portfolio.drawdown(marks)
            if dd >= settings.max_drawdown_pct:
                reasons.append(
                    f"drawdown {dd:.2%} has reached the {settings.max_drawdown_pct:.2%} limit"
                )

        if intent.action == "BUY" and equity > 0:
            available = portfolio.available_cash()
            if available < turnover + fee:
                reasons.append("insufficient available cash")
            cash_after = portfolio.cash - turnover - fee
            locked = portfolio.locked_collateral
            available_after = cash_after - locked
            reserve = settings.min_cash_reserve_pct * equity
            if available_after < reserve:
                reasons.append(
                    f"cash reserve would fall below {settings.min_cash_reserve_pct:.0%} of equity"
                )
            long_after = portfolio.long_market_value(marks) + turnover
            if long_after > settings.max_invested_pct * equity + 1e-6:
                reasons.append("maximum invested capital would be exceeded")
            ticker_after = turnover
            if pos and pos.side == "long":
                ticker_after += pos.quantity * marks.get(intent.ticker, intent.price)
            if ticker_after > settings.max_position_pct * equity + 1e-6:
                reasons.append(
                    f"position would exceed {settings.max_position_pct:.0%} of equity"
                )

        if intent.action == "SHORT" and equity > 0:
            notional = turnover
            coll = notional * settings.short_collateral_pct
            extra = max(0.0, coll - notional) + fee
            if portfolio.available_cash() < extra:
                reasons.append("insufficient cash for short collateral")
            ticker_after = notional
            if pos and pos.side == "short":
                ticker_after += pos.quantity * marks.get(intent.ticker, intent.price)
            if ticker_after > settings.max_position_pct * equity + 1e-6:
                reasons.append(
                    f"short position would exceed {settings.max_position_pct:.0%} of equity"
                )
            gross_after = portfolio.gross_exposure(marks) + notional
            if gross_after > settings.max_invested_pct * equity + 1e-6:
                reasons.append("gross exposure would exceed the invested-capital limit")

        if intent.action == "COVER":
            if portfolio.cash < turnover + fee:
                reasons.append("insufficient cash to cover the short")

        # De-duplicate while keeping order.
        unique: list[str] = []
        for reason in reasons:
            if reason not in unique:
                unique.append(reason)
        return RiskResult(approved=not unique, reasons=unique)
