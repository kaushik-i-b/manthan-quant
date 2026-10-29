"""Cash, positions, and P&L.

Fills are applied once. Pending intents are not part of cash or holdings.
Fees reduce cash when the fill is confirmed and are not also subtracted from
the displayed gross price P&L. Net P&L is equity minus starting capital.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.types import Fill


def money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


@dataclass
class Position:
    ticker: str
    side: str  # long | short
    quantity: int
    avg_price: float
    opened_day: int
    entry_fee: float = 0.0

    def notional(self, mark: float) -> float:
        return self.quantity * mark


@dataclass
class ClosedTrade:
    ticker: str
    side: str
    quantity: int
    avg_price: float
    exit_price: float
    opened_day: int
    closed_day: int
    gross_pnl: float
    fees: float
    net_pnl: float


@dataclass
class Portfolio:
    starting_capital: float
    cash: float
    short_collateral_pct: float
    positions: dict[str, Position] = field(default_factory=dict)
    locked_collateral: float = 0.0
    realized_gross: float = 0.0
    fees_paid: float = 0.0
    brokerage_paid: float = 0.0
    taxes_paid: float = 0.0
    closed: list[ClosedTrade] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    applied_ids: set[str] = field(default_factory=set)
    equity_history: list[dict] = field(default_factory=list)
    peak_equity: float = 0.0
    max_drawdown: float = 0.0
    frozen: set[str] = field(default_factory=set)
    valuation: str = "mock_exchange"
    reliable: bool = True

    def __post_init__(self) -> None:
        self.peak_equity = self.starting_capital

    @classmethod
    def start(cls, capital: float, collateral_pct: float) -> "Portfolio":
        book = cls(starting_capital=money(capital), cash=money(capital), short_collateral_pct=collateral_pct)
        return book

    def position(self, ticker: str) -> Position | None:
        return self.positions.get(ticker)

    def mark_map(self, marks: dict[str, float]) -> dict[str, float]:
        out = {}
        for ticker, pos in self.positions.items():
            out[ticker] = marks.get(ticker, pos.avg_price)
        return out

    def long_market_value(self, marks: dict[str, float]) -> float:
        return sum(
            pos.quantity * marks.get(pos.ticker, pos.avg_price)
            for pos in self.positions.values()
            if pos.side == "long"
        )

    def short_liability(self, marks: dict[str, float]) -> float:
        return sum(
            pos.quantity * marks.get(pos.ticker, pos.avg_price)
            for pos in self.positions.values()
            if pos.side == "short"
        )

    def gross_exposure(self, marks: dict[str, float]) -> float:
        return self.long_market_value(marks) + self.short_liability(marks)

    def unrealized(self, marks: dict[str, float]) -> float:
        total = 0.0
        for pos in self.positions.values():
            mark = marks.get(pos.ticker, pos.avg_price)
            if pos.side == "long":
                total += (mark - pos.avg_price) * pos.quantity
            else:
                total += (pos.avg_price - mark) * pos.quantity
        return total

    def equity(self, marks: dict[str, float]) -> float:
        return self.cash + self.long_market_value(marks) - self.short_liability(marks)

    def available_cash(self) -> float:
        return self.cash - self.locked_collateral

    def drawdown(self, marks: dict[str, float]) -> float:
        eq = self.equity(marks)
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - eq) / self.peak_equity)

    def snapshot_equity(self, sim_day: int, marks: dict[str, float]) -> dict:
        eq = self.equity(marks)
        self.peak_equity = max(self.peak_equity, eq)
        dd = 0.0 if self.peak_equity <= 0 else (self.peak_equity - eq) / self.peak_equity
        self.max_drawdown = max(self.max_drawdown, dd)
        row = {
            "sim_day": sim_day,
            "equity": money(eq),
            "cash": money(self.cash),
            "invested": money(self.long_market_value(marks)),
            "gross_exposure": money(self.gross_exposure(marks)),
            "pnl": money(eq - self.starting_capital),
            "drawdown": dd,
        }
        self.equity_history.append(row)
        return row

    def apply_fill(self, fill: Fill) -> None:
        if fill.status != "FILLED":
            return
        if fill.client_order_id in self.applied_ids:
            return
        fee = money(fill.brokerage + fill.taxes_and_fees)
        self.applied_ids.add(fill.client_order_id)
        self.fills.append(fill)
        self.fees_paid = money(self.fees_paid + fee)
        self.brokerage_paid = money(self.brokerage_paid + fill.brokerage)
        self.taxes_paid = money(self.taxes_paid + fill.taxes_and_fees)
        pos = self.positions.get(fill.ticker)
        if fill.action == "BUY":
            self._increase(fill, "long", fee)
        elif fill.action == "SHORT":
            notional = fill.quantity * fill.price
            self.cash = money(self.cash + notional - fee)
            self.locked_collateral = money(self.locked_collateral + notional * self.short_collateral_pct)
            self._increase(fill, "short", fee, touch_cash=False)
        elif fill.action == "SELL":
            self._decrease(fill, "long", fee)
        elif fill.action == "COVER":
            self._decrease(fill, "short", fee)
        else:
            raise ValueError(fill.action)

    def _increase(self, fill: Fill, side: str, fee: float, touch_cash: bool = True) -> None:
        if touch_cash:
            self.cash = money(self.cash - fill.quantity * fill.price - fee)
        pos = self.positions.get(fill.ticker)
        if pos is None:
            self.positions[fill.ticker] = Position(
                ticker=fill.ticker,
                side=side,
                quantity=fill.quantity,
                avg_price=fill.price,
                opened_day=fill.sim_day,
                entry_fee=fee,
            )
            return
        if pos.side != side:
            raise RuntimeError(f"cannot increase {side} over existing {pos.side}")
        new_qty = pos.quantity + fill.quantity
        pos.avg_price = (pos.avg_price * pos.quantity + fill.price * fill.quantity) / new_qty
        pos.quantity = new_qty
        pos.entry_fee = money(pos.entry_fee + fee)

    def _decrease(self, fill: Fill, side: str, fee: float) -> None:
        pos = self.positions.get(fill.ticker)
        if pos is None or pos.side != side or fill.quantity > pos.quantity:
            raise RuntimeError(f"invalid {fill.action} for {fill.ticker}")
        alloc = pos.entry_fee * (fill.quantity / pos.quantity)
        if side == "long":
            gross = (fill.price - pos.avg_price) * fill.quantity
            self.cash = money(self.cash + fill.quantity * fill.price - fee)
        else:
            gross = (pos.avg_price - fill.price) * fill.quantity
            release = fill.quantity * pos.avg_price * self.short_collateral_pct
            self.locked_collateral = money(max(0.0, self.locked_collateral - release))
            self.cash = money(self.cash - fill.quantity * fill.price - fee)
        net = gross - alloc - fee
        self.realized_gross = money(self.realized_gross + gross)
        self.closed.append(
            ClosedTrade(
                ticker=fill.ticker,
                side=side,
                quantity=fill.quantity,
                avg_price=pos.avg_price,
                exit_price=fill.price,
                opened_day=pos.opened_day,
                closed_day=fill.sim_day,
                gross_pnl=money(gross),
                fees=money(alloc + fee),
                net_pnl=money(net),
            )
        )
        pos.quantity -= fill.quantity
        pos.entry_fee = money(pos.entry_fee - alloc)
        if pos.quantity == 0:
            del self.positions[fill.ticker]

    def wins(self) -> int:
        return sum(1 for trade in self.closed if trade.net_pnl > 0)

    def losses(self) -> int:
        return sum(1 for trade in self.closed if trade.net_pnl <= 0)

    def win_rate(self) -> float | None:
        if not self.closed:
            return None
        return self.wins() / len(self.closed)
