"""Portfolio accounting: cash, holdings, shorts, costs, equity history."""
from __future__ import annotations

from app.config import settings
from app.models.schemas import Action, PortfolioSnapshot, Position


class Portfolio:
    def __init__(self, starting: float | None = None) -> None:
        s = starting or settings.STARTING_CAPITAL
        self.starting = s
        self.cash = s
        self.positions: dict[str, Position] = {}
        self.realized = 0.0
        self.fees_paid = 0.0
        self.peak = s
        self.equity_hist: list[dict] = []
        self.trade_count = 0
        self.wins = 0

    def pos(self, ticker: str) -> Position:
        if ticker not in self.positions:
            self.positions[ticker] = Position(ticker=ticker)
        return self.positions[ticker]

    def cost_of(self, qty: int, price: float, action: Action) -> float:
        gross = qty * price
        fee = gross * (settings.BROKERAGE_PCT + settings.STT_PCT)
        dp = settings.DP_CHARGE if action == Action.SELL else 0.0
        return fee + dp

    def apply_fill(self, ticker: str, action: Action, qty: int, price: float) -> dict:
        p = self.pos(ticker)
        fee = self.cost_of(qty, price, action)
        self.fees_paid += fee
        if action == Action.BUY:
            new_qty = p.qty + qty
            p.avg_price = (p.avg_price * p.qty + price * qty) / new_qty if new_qty else 0
            p.qty = new_qty
            self.cash -= qty * price + fee
        elif action == Action.SELL:
            qty = min(qty, p.qty)
            pnl = (price - p.avg_price) * qty - fee
            self.realized += pnl
            self.cash += qty * price - fee
            p.qty -= qty
            if p.qty == 0:
                p.avg_price = 0
            self.trade_count += 1
            if pnl > 0:
                self.wins += 1
        elif action == Action.SHORT:
            new_q = p.short_qty + qty
            p.short_avg = (p.short_avg * p.short_qty + price * qty) / new_q if new_q else 0
            p.short_qty = new_q
            self.cash += qty * price - fee  # credit proceeds, collateral tracked via risk
        elif action == Action.COVER:
            qty = min(qty, p.short_qty)
            pnl = (p.short_avg - price) * qty - fee
            self.realized += pnl
            self.cash -= qty * price + fee
            p.short_qty -= qty
            if p.short_qty == 0:
                p.short_avg = 0
            self.trade_count += 1
            if pnl > 0:
                self.wins += 1
        return {"fee": fee, "cash": self.cash}

    def equity(self, prices: dict[str, float]) -> float:
        eq = self.cash
        for t, p in self.positions.items():
            px = prices.get(t, p.avg_price)
            eq += p.qty * px - p.short_qty * px
        return eq

    def snapshot(self, prices: dict[str, float], sim_day: int) -> PortfolioSnapshot:
        eq = self.equity(prices)
        self.peak = max(self.peak, eq)
        dd = (self.peak - eq) / self.peak if self.peak else 0
        invested = sum(p.qty * prices.get(t, p.avg_price) for t, p in self.positions.items())
        unreal = sum((prices.get(t, p.avg_price) - p.avg_price) * p.qty for t, p in self.positions.items())
        snap = PortfolioSnapshot(cash=round(self.cash, 2), equity=round(eq, 2),
                                 invested=round(invested, 2), realized_pnl=round(self.realized, 2),
                                 unrealized_pnl=round(unreal, 2),
                                 total_return_pct=round((eq - self.starting) / self.starting * 100, 3),
                                 drawdown_pct=round(dd * 100, 3),
                                 positions=dict(self.positions), sim_day=sim_day)
        self.equity_hist.append({"sim_day": sim_day, "equity": round(eq, 2), "cash": round(self.cash, 2)})
        if len(self.equity_hist) > 2000:
            self.equity_hist = self.equity_hist[-2000:]
        return snap

    def reset(self) -> None:
        self.__init__(self.starting)
