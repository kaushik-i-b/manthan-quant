"""Single-writer execution queue: Signal -> Risk -> Intent -> Submit -> Reconcile -> Audit."""
from __future__ import annotations

import asyncio
import uuid
from collections import deque

from app.config import settings
from app.execution.api_client import ApiClient
from app.models.schemas import Action, OrderResult, OrderStatus, Signal
from app.portfolio.manager import Portfolio
from app.risk.engine import RiskEngine


class Executor:
    def __init__(self, api: ApiClient, risk: RiskEngine, portfolio: Portfolio) -> None:
        self.api = api
        self.risk = risk
        self.portfolio = portfolio
        self.queue: asyncio.Queue[Signal] = asyncio.Queue(maxsize=200)
        self.orders: deque[dict] = deque(maxlen=500)
        self.seen: set[str] = set()  # duplicate prevention per ticker+day+action
        self.outstanding = 0
        self.data_stale = False
        self.sim_active = True

    def _dedupe_key(self, s: Signal, qty: int) -> str:
        return f"{s.ticker}:{s.sim_day}:{s.action}:{qty}"

    async def run_forever(self, prices: dict, broadcast) -> None:
        while True:
            sig = await self.queue.get()
            try:
                await self.process(sig, prices, broadcast)
            finally:
                self.queue.task_done()

    async def process(self, sig: Signal, prices: dict, broadcast) -> OrderResult | None:
        if sig.action == Action.HOLD:
            await broadcast("strategy.signal", sig.model_dump(mode="json"))
            return None
        price = prices.get(sig.ticker, 0)
        equity = self.portfolio.equity(prices)
        dd = self.portfolio.snapshot(prices, sig.sim_day).drawdown_pct / 100
        dec = self.risk.evaluate(sig, self.portfolio.cash, equity, self.portfolio.positions,
                                 price, dd, self.outstanding, self.sim_active,
                                 self.data_stale, self.api.ok)
        sig.risk_passed = dec.passed
        sig.risk_reason = dec.reason
        await broadcast("strategy.signal", sig.model_dump(mode="json"))
        if not dec.passed:
            await broadcast("risk.alert", {"ticker": sig.ticker, "reason": dec.reason, "sim_day": sig.sim_day})
            self.orders.append({"ticker": sig.ticker, "action": sig.action.value, "status": "REJECTED",
                                "reason": dec.reason, "sim_day": sig.sim_day})
            return None
        key = self._dedupe_key(sig, dec.quantity)
        if key in self.seen:
            return None
        self.seen.add(key)
        intent = {"client_id": f"{key}-{uuid.uuid4().hex[:6]}", "ticker": sig.ticker,
                  "action": sig.action.value, "quantity": dec.quantity, "ref_price": price}
        await broadcast("order.intent", intent)
        self.outstanding += 1
        try:
            resp = await self.api.submit_order({"ticker": sig.ticker, "action": sig.action.value,
                                                "quantity": dec.quantity})
        finally:
            self.outstanding -= 1
        if resp.get("ok"):
            fill_px = price  # simulator executes at current-candle close
            self.portfolio.apply_fill(sig.ticker, sig.action, dec.quantity, fill_px)
            fee = self.portfolio.cost_of(dec.quantity, fill_px, sig.action)
            res = OrderResult(client_id=intent["client_id"], ticker=sig.ticker, action=sig.action,
                              quantity=dec.quantity, status=OrderStatus.CONFIRMED,
                              fill_price=fill_px, cost=round(dec.quantity * fill_px + fee, 2),
                              reason="mock-fill" if resp.get("mock") else "venue-fill", sim_day=sig.sim_day)
            self.risk.record_fill()
        else:
            res = OrderResult(client_id=intent["client_id"], ticker=sig.ticker, action=sig.action,
                              quantity=dec.quantity, status=OrderStatus.FAILED,
                              reason=str(resp.get("error", resp))[:300], sim_day=sig.sim_day)
        self.orders.append({"ticker": res.ticker, "action": res.action.value, "quantity": res.quantity,
                            "status": res.status.value, "fill_price": res.fill_price,
                            "reason": res.reason, "sim_day": res.sim_day})
        await broadcast("order.result", res.model_dump(mode="json"))
        await broadcast("portfolio.updated", self.portfolio.snapshot(prices, sig.sim_day).model_dump(mode="json"))
        return res
