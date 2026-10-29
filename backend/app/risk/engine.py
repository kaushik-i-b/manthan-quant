"""Independent risk engine. Every signal evaluated before any order."""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.models.schemas import Action, Signal


@dataclass
class RiskDecision:
    passed: bool
    reason: str
    quantity: int = 0


class RiskEngine:
    def __init__(self, s=None) -> None:
        self.s = s or settings
        self.paused: bool = False
        self.pause_reason: str = ""
        self.orders_today: int = 0
        self._day: int = -1
        self.violations: list[dict] = []

    def set_paused(self, paused: bool, reason: str = "") -> None:
        self.paused = paused
        self.pause_reason = reason

    def _new_day(self, sim_day: int) -> None:
        if sim_day != self._day:
            self._day = sim_day
            self.orders_today = 0

    def evaluate(self, signal: Signal, cash: float, equity: float, positions: dict,
                 price: float, drawdown: float, outstanding: int,
                 sim_active: bool, data_stale: bool, api_ok: bool) -> RiskDecision:
        self._new_day(signal.sim_day)
        if signal.action == Action.HOLD:
            return RiskDecision(True, "HOLD needs no risk check", 0)
        if self.paused:
            return self._rej(f"Trading paused: {self.pause_reason}")
        if not sim_active:
            return self._rej("Simulation not in TRADING stage")
        if not api_ok and not self.s.MOCK_MODE:
            return self._rej("API connectivity unreliable")
        if data_stale:
            return self._rej("Market data stale")
        if drawdown >= self.s.MAX_DRAWDOWN_PCT:
            return self._rej(f"Max drawdown breached {drawdown:.2%} >= {self.s.MAX_DRAWDOWN_PCT:.2%}")
        if self.orders_today >= self.s.MAX_ORDERS_PER_DAY:
            return self._rej(f"Max orders/day {self.s.MAX_ORDERS_PER_DAY} reached")
        if outstanding >= self.s.MAX_OUTSTANDING_ORDERS:
            return self._rej("Too many outstanding orders")
        if price <= 0:
            return self._rej("Invalid price")
        # position sizing: volatility-aware, capped at MAX_POSITION_PCT of equity
        vol = float(signal.indicators.get("volatility") or 0.03)
        vol_scale = max(0.25, min(1.0, 0.03 / max(vol, 0.005)))
        target_value = equity * self.s.MAX_POSITION_PCT * vol_scale * (0.5 + signal.score * 0.5)
        qty = int(target_value // price)
        if qty <= 0:
            return self._rej(f"Quantity rounds to 0 (price={price:.2f})")
        cost = qty * price * (1 + self.s.BROKERAGE_PCT + self.s.STT_PCT)
        reserve = equity * self.s.MIN_CASH_RESERVE_PCT
        if signal.action in (Action.BUY,):
            if cash - cost < reserve:
                return self._rej(f"Insufficient cash after reserve: need {cost:,.0f}, cash {cash:,.0f}, reserve {reserve:,.0f}")
            pos = positions.get(signal.ticker)
            cur_val = (pos.qty * price) if pos else 0
            if (cur_val + qty * price) / max(equity, 1) > self.s.MAX_CONCENTRATION_PCT:
                return self._rej("Concentration limit breached")
            if (equity - cash + cost) / max(equity, 1) > self.s.MAX_INVESTED_PCT:
                return self._rej("Max invested capital breached")
        if signal.action in (Action.SELL,) and signal.ticker in positions:
            held = positions[signal.ticker].qty
            if held <= 0:
                return self._rej("No long position to sell")
            qty = min(qty, held)
        if signal.action == Action.SHORT:
            collateral = cost * 1.0
            if cash < collateral + reserve:
                return self._rej("Short collateral insufficient")
        return RiskDecision(True, f"Passed: qty={qty} vol_scale={vol_scale:.2f}", qty)

    def record_fill(self) -> None:
        self.orders_today += 1

    def _rej(self, reason: str) -> RiskDecision:
        self.violations.append({"reason": reason})
        return RiskDecision(False, reason, 0)
