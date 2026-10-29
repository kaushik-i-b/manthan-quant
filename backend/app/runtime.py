"""Composition root for the mock exchange, strategy loop, and desk state.

The feed task is the only order writer in mock mode. A lock guards the
venue path as well. Dashboard subscribers are optional: if nobody is
listening, publishing is a no-op beyond a bounded ring.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.api.inventory import local_portal_panel
from app.config import Settings
from app.execution.client import ApiError, TradingApiClient
from app.execution.costs import quote_cost
from app.execution.rate_limit import RateLimiter
from app.execution.templates import TemplateError, load_template, render
from app.indicators.engine import IndicatorEngine
from app.logging_setup import log
from app.market.book import NewsTape, TickerTape
from app.market.bus import EventBus
from app.market.synthetic import SYNTHETIC_EPOCH, SyntheticDataset, build_dataset
from app.models.types import Candle, Fill, OrderIntent
from app.monitoring.latency import LatencyTracker
from app.persistence.store import AuditStore
from app.portfolio.accounting import Portfolio, money
from app.risk.engine import RiskContext, RiskEngine
from app.sentiment.lexicon import annotate
from app.simulation.lifecycle import LifecycleManager
from app.strategies.propose import Proposal, propose
from app.strategies.selector import StrategySelector

logger = logging.getLogger("manthan.runtime")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


class TradingRuntime:
    def __init__(self, settings: Settings, *, persist: bool = True) -> None:
        self.settings = settings
        self.persist = persist
        self.bus = EventBus()
        self.lifecycle = LifecycleManager(settings.heartbeat_interval_sec)
        self.selector = StrategySelector()
        self.risk = RiskEngine(settings)
        self.portfolio = Portfolio.start(settings.initial_capital, settings.short_collateral_pct)
        self.portfolio.valuation = "mock_exchange" if settings.market_mode == "mock" else "estimated"
        self.limiter = RateLimiter(settings.api_rate_limit_per_min)
        self.client = TradingApiClient(settings, self.limiter)
        self.store = AuditStore(settings.db_path)
        self.latency = LatencyTracker()
        self.dataset: SyntheticDataset | None = None
        self.names: dict[str, str] = {}
        self.tickers: list[str] = []
        self.tapes: dict[str, TickerTape] = {}
        self.indicators: dict[str, IndicatorEngine] = {}
        self.enriched: dict[str, list[dict]] = {}
        self.snaps = {}
        self.marks: dict[str, float] = {}
        self.news = NewsTape()
        self.signals: dict[str, dict] = {}
        self.decisions: deque[dict] = deque(maxlen=400)
        self.trade_log: list[dict] = []
        self.orders: deque[dict] = deque(maxlen=400)
        self.audit: deque[dict] = deque(maxlen=500)
        self.rejections: deque[dict] = deque(maxlen=80)
        self.seen_order_ids: set[str] = set()
        self.orders_today: dict[int, int] = {}
        self.outstanding = 0
        self.last_entry_day: dict[str, int] = {}
        self.sim_day = -1
        self.order_seq = 0
        self.decision_seq = 0
        self.rejected_count = 0
        self.strategy_mode = "adaptive"
        self.paused = False
        self.outage = False
        self.feed_status = "idle"
        self.api_reachable: bool | None = None
        self.kafka_connected = False
        self.kafka_lag: int | None = None
        self.last_event_wall = 0.0
        self._reject_done = False
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._order_lock = asyncio.Lock()
        self.milestones = {
            "market_data": False,
            "indicators": False,
            "signal": False,
            "risk_pass": False,
            "fill": False,
            "pnl_updated": False,
            "risk_reject": False,
            "outage_recovered": False,
        }

    def bootstrap(self) -> None:
        if self.settings.market_mode != "mock":
            self.feed_status = "venue_unconfigured" if self.settings.market_mode == "venue" else "kafka_idle"
            return
        self.dataset = build_dataset(self.settings.synthetic_seed, self.settings.synthetic_days)
        self.names = dict(self.dataset.names)
        self.tickers = list(self.dataset.candles)
        for ticker in self.tickers:
            self.tapes[ticker] = TickerTape()
            self.indicators[ticker] = IndicatorEngine()
            self.enriched[ticker] = []
        self.feed_status = "ready"

    async def start(self) -> None:
        if self.persist:
            await self.store.open()
        self.bootstrap()
        if self.settings.market_mode == "mock" and self.dataset is not None:
            for day in range(self.settings.warmup_days):
                await self.play_day(day, trade=False, delay=False, publish=False)
            await self._heartbeat_once()
            self.lifecycle.stage = "PREFLIGHT"
            self._tasks.append(asyncio.create_task(self._heartbeat_loop(), name="heartbeat"))
            self._tasks.append(asyncio.create_task(self._feed_loop(), name="feed"))
            if self.settings.market_mode == "venue":
                self._tasks.append(asyncio.create_task(self._stage_loop(), name="stage"))
        elif self.settings.kafka_enabled:
            self._tasks.append(asyncio.create_task(self._heartbeat_loop(), name="heartbeat"))
            self._tasks.append(asyncio.create_task(self._kafka_loop(), name="kafka"))
        else:
            self._tasks.append(asyncio.create_task(self._heartbeat_loop(), name="heartbeat"))
            if self.settings.market_mode == "venue":
                self._tasks.append(asyncio.create_task(self._stage_loop(), name="stage"))
        log(logger, logging.INFO, "runtime started", mode=self.settings.market_mode, dry_run=self.settings.dry_run)

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        await self.client.aclose()
        if self.persist:
            await self.store.close()

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return

    async def _heartbeat_loop(self) -> None:
        while not self._stop.is_set():
            await self._heartbeat_once()
            await self._sleep(self.settings.heartbeat_interval_sec)

    async def _heartbeat_once(self) -> None:
        if self.settings.market_mode != "venue":
            self.lifecycle.ack(time.monotonic())
            self._publish_health()
            return
        path = self.settings.venue_heartbeat_template_path
        if not path:
            self.lifecycle.fail("official heartbeat payload is not configured")
            self._publish_health()
            return
        try:
            template = load_template(path)
            payload = render(template, {"stage": self.lifecycle.stage, "ts": utcnow()})
            await self.client.post_heartbeat(payload)
            self.lifecycle.ack(time.monotonic())
        except (TemplateError, ApiError, OSError) as exc:
            self.lifecycle.fail(str(exc)[:180])
        self._publish_health()

    async def _stage_loop(self) -> None:
        while not self._stop.is_set():
            field = self.settings.venue_stage_stage_field
            if not field:
                self.lifecycle.stage = "UNKNOWN"
                self.lifecycle.fail("official stage field is not configured")
            else:
                try:
                    raw = await self.client.get_stage()
                    self.api_reachable = True
                    value = raw.get(field) if isinstance(raw, dict) else None
                    if value is None:
                        self.lifecycle.stage = "UNKNOWN"
                    elif str(value) == self.settings.venue_stage_active_value:
                        self.lifecycle.stage = "TRADING"
                    else:
                        self.lifecycle.stage = "HALTED"
                except (ApiError, OSError) as exc:
                    self.api_reachable = False
                    self.lifecycle.fail(str(exc)[:180])
            self.bus.publish({"type": "simulation.stage", "data": self.lifecycle_view()})
            await self._sleep(10)

    async def _kafka_loop(self) -> None:
        if not self.settings.kafka_group_id.strip():
            self.kafka_connected = False
            self.lifecycle.fail("Kafka consumer group is not configured")
            self._publish_health()
            return
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError:
            self.lifecycle.fail("aiokafka is not installed")
            return
        consumer = AIOKafkaConsumer(
            self.settings.kafka_topic_ticks,
            self.settings.kafka_topic_news,
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
            group_id=self.settings.kafka_group_id,
            enable_auto_commit=False,
            auto_offset_reset="latest",
        )
        await consumer.start()
        self.kafka_connected = True
        self._publish_health()
        try:
            async for msg in consumer:
                if self._stop.is_set():
                    break
                await self._handle_kafka_message(msg)
                await consumer.commit()
        finally:
            self.kafka_connected = False
            await consumer.stop()
            self._publish_health()

    async def _handle_kafka_message(self, msg) -> None:
        from app.market.parse import SchemaRejected, loads, parse_news, parse_tick

        try:
            data = loads(msg.value)
            topic = msg.topic
            if topic == self.settings.kafka_topic_ticks:
                candle = parse_tick(data, None)
                self._install_ticker(candle.ticker)
                if self.tapes[candle.ticker].add(candle):
                    snap = self.indicators[candle.ticker].update(candle)
                    self.snaps[candle.ticker] = snap
                    self.marks[candle.ticker] = candle.close
                    self.sim_day = max(self.sim_day, candle.sim_day)
                    self.last_event_wall = time.monotonic()
                    row = self._candle_row(candle, snap)
                    self.enriched[candle.ticker].append(row)
                    self.milestones["market_data"] = True
                    if snap.ready:
                        self.milestones["indicators"] = True
                    self.bus.publish({"type": "market.tick", "data": row})
            elif topic == self.settings.kafka_topic_news:
                item = parse_news(data, None)
                if self.news.add(item):
                    scored = annotate(item, item.sim_day)
                    self.bus.publish({"type": "market.news", "data": self._news_row(scored)})
        except (SchemaRejected, ValueError) as exc:
            self._remember_audit("schema_rejected", {"error": str(exc)})

    def _install_ticker(self, ticker: str) -> None:
        if ticker not in self.tapes:
            self.tapes[ticker] = TickerTape()
            self.indicators[ticker] = IndicatorEngine()
            self.enriched[ticker] = []
            self.names.setdefault(ticker, ticker)
            self.tickers.append(ticker)

    async def _feed_loop(self) -> None:
        assert self.dataset is not None
        self.feed_status = "preflight"
        self.lifecycle.stage = "PREFLIGHT"
        self._publish_health()
        if self.settings.replay_mode == "realtime":
            await self._sleep(1.2)
        if self._stop.is_set():
            return
        self.lifecycle.stage = "TRADING"
        self.feed_status = "live"
        self.bus.publish({"type": "simulation.stage", "data": self.lifecycle_view()})
        self._publish_health()
        for day in range(self.settings.warmup_days, self.dataset.days):
            if self._stop.is_set():
                break
            while self.outage and not self._stop.is_set():
                await self._sleep(0.25)
            if self._stop.is_set():
                break
            delay = self.settings.replay_mode == "realtime"
            await self.play_day(day, trade=True, delay=delay, publish=True)
            extra = self.settings.sim_day_seconds - (self.settings.news_delay_ms / 1000.0 if delay else 0.0)
            if delay and extra > 0:
                await self._sleep(extra)
        if not self._stop.is_set():
            self.lifecycle.stage = "ENDED"
            self.feed_status = "ended"
            self.bus.publish({"type": "simulation.stage", "data": self.lifecycle_view()})
            self._publish_health()

    async def play_day(self, day: int, *, trade: bool, delay: bool, publish: bool) -> None:
        if self.dataset is None:
            return
        self._apply_quotes(day, publish)
        if delay and self.settings.news_delay_ms > 0:
            await self._sleep(self.settings.news_delay_ms / 1000.0)
        self._apply_news(day, publish)
        if trade:
            await self._evaluate_day(day, publish)
        self.portfolio.snapshot_equity(day, self.marks)
        if publish:
            self.bus.publish({"type": "portfolio.updated", "data": self.portfolio_view()})

    def _apply_quotes(self, day: int, publish: bool) -> None:
        assert self.dataset is not None
        self.sim_day = day
        self.last_event_wall = time.monotonic()
        for ticker in self.tickers:
            candle = self.dataset.candles[ticker][day]
            if not self.tapes[ticker].add(candle):
                continue
            snap = self.indicators[ticker].update(candle)
            self.snaps[ticker] = snap
            self.marks[ticker] = candle.close
            row = self._candle_row(candle, snap)
            self.enriched[ticker].append(row)
            self.milestones["market_data"] = True
            if snap.ready:
                self.milestones["indicators"] = True
            if publish:
                self.bus.publish({"type": "market.tick", "data": row})

    def _apply_news(self, day: int, publish: bool) -> None:
        assert self.dataset is not None
        for item in self.dataset.news:
            if item.sim_day != day:
                continue
            if not self.news.add(item):
                continue
            scored = annotate(item, day)
            if publish:
                self.bus.publish({"type": "market.news", "data": self._news_row(scored)})

    async def _evaluate_day(self, day: int, publish: bool) -> None:
        for ticker in self.tickers:
            await self._evaluate_ticker(ticker, day, publish)
        await self._maybe_probe(day, publish)

    async def _evaluate_ticker(self, ticker: str, day: int, publish: bool) -> None:
        started = time.perf_counter()
        snap = self.snaps.get(ticker)
        if snap is None:
            return
        raw_news = self.news.latest(ticker, day)
        news = annotate(raw_news, day) if raw_news else None
        data_ok = not self._stale()
        selection = self.selector.select(
            snap,
            news,
            data_ok=data_ok,
            drawdown=self.portfolio.drawdown(self.marks),
            max_drawdown=self.settings.max_drawdown_pct,
        )
        close = self.marks[ticker]
        position = self.portfolio.position(ticker)
        equity = self.portfolio.equity(self.marks)
        cooldown = ticker in self.last_entry_day and day - self.last_entry_day[ticker] < self.settings.cooldown_days
        proposal = propose(
            mode=self.strategy_mode,
            settings=self.settings,
            snap=snap,
            selection=selection,
            position=position,
            close=close,
            equity=equity,
            sim_day=day,
            atr=snap.atr14,
            in_cooldown=cooldown,
        )
        self.latency.add((time.perf_counter() - started) * 1000.0)
        self.signals[ticker] = {
            "action": proposal.action,
            "signal_score": round(selection.action_bias, 4),
            "score_type": "heuristic",
            "strategy": proposal.strategy,
            "regime": selection.regime,
            "trend": self._trend_label(snap),
        }
        if proposal.action == "HOLD" or proposal.quantity < 1:
            reason = proposal.reason
            if proposal.action != "HOLD" and proposal.quantity < 1:
                reason = "Position size rounded to zero, so the book held. " + proposal.reason
            await self._remember_decision(
                self._decision_body(
                    ticker, day, "HOLD", selection, proposal, news, reason, None, False, None
                )
            )
            if publish:
                self.bus.publish({"type": "strategy.signal", "data": self.latest_decision(ticker)})
            return
        self.milestones["signal"] = True
        intent = OrderIntent(
            client_order_id=f"{ticker}:{day}:{proposal.action}:{self.strategy_mode}:{proposal.strategy}",
            ticker=ticker,
            action=proposal.action,  # type: ignore[arg-type]
            quantity=proposal.quantity,
            price=close,
            sim_day=day,
            strategy=proposal.strategy,
            reason=proposal.reason,
            signal_score=selection.action_bias,
            is_exit=proposal.is_exit,
        )
        await self._execute_intent(intent, selection, proposal, news, publish)

    async def _maybe_probe(self, day: int, publish: bool) -> None:
        if not self.settings.demo_probe or self.settings.market_mode != "mock" or self.strategy_mode != "adaptive":
            return
        if day != self.settings.demo_reject_day or self._reject_done:
            return
        if "RELIANCE" not in self.marks:
            return
        self._reject_done = True
        price = self.marks["RELIANCE"]
        intent = OrderIntent(
            client_order_id=f"probe:RELIANCE:{day}:BUY",
            ticker="RELIANCE",
            action="BUY",
            quantity=1_000_000_000,
            price=price,
            sim_day=day,
            strategy="risk_probe",
            reason="Demonstration probe: a billion-share buy must be rejected by the risk engine.",
            signal_score=1.0,
            is_exit=False,
        )
        selection = self.selector.select(
            self.snaps["RELIANCE"],
            None,
            data_ok=not self._stale(),
            drawdown=self.portfolio.drawdown(self.marks),
            max_drawdown=self.settings.max_drawdown_pct,
        )
        proposal = Proposal("BUY", intent.quantity, False, intent.reason, "risk_probe")
        await self._execute_intent(intent, selection, proposal, None, publish)

    async def _execute_intent(self, intent: OrderIntent, selection, proposal: Proposal, news, publish: bool) -> None:
        async with self._order_lock:
            result = self.risk.evaluate(intent, self.portfolio, self._risk_context())
            approved = result.approved
            rejection = None if approved else "; ".join(result.reasons)
            if not approved:
                self.rejected_count += 1
                self.seen_order_ids.add(intent.client_order_id)
                if intent.strategy == "risk_probe":
                    self.milestones["risk_reject"] = True
                body = self._decision_body(
                    intent.ticker,
                    intent.sim_day,
                    intent.action,
                    selection,
                    proposal,
                    news,
                    intent.reason + " Rejected: " + (rejection or ""),
                    False,
                    False,
                    rejection,
                )
                body["signal_score"] = round(intent.signal_score, 4)
                await self._remember_decision(body)
                order = self._order_row(intent, "REJECTED", rejection or "rejected", 0, 0, "")
                await self._remember_order(order)
                self.rejections.append(body)
                if publish:
                    self.bus.publish({"type": "strategy.signal", "data": body})
                    self.bus.publish({"type": "risk.alert", "data": body})
                    self.bus.publish({"type": "order.result", "data": order})
                return

            self.seen_order_ids.add(intent.client_order_id)
            self.orders_today[intent.sim_day] = self.orders_today.get(intent.sim_day, 0) + 1
            self.milestones["risk_pass"] = True
            fill = await self._fill(intent)
            executed = fill.status == "FILLED"
            if executed:
                self.portfolio.apply_fill(fill)
                if intent.action in {"BUY", "SHORT"}:
                    self.last_entry_day[intent.ticker] = intent.sim_day
                self.milestones["fill"] = True
                if abs(self.portfolio.equity(self.marks) - self.portfolio.starting_capital) >= 0.5:
                    self.milestones["pnl_updated"] = True
            elif fill.status == "UNKNOWN":
                self.portfolio.frozen.add(intent.ticker)
                self.outstanding += 1
                self.portfolio.reliable = self.settings.market_mode != "venue"
            reason = intent.reason
            if executed:
                reason = f"{intent.reason} Filled {intent.quantity} @ {intent.price:.2f} on the {fill.venue} book."
            elif fill.status == "UNKNOWN":
                reason = f"{intent.reason} Submission status is unknown, so the ticker was frozen and the order was not retried."
            else:
                reason = f"{intent.reason} Failed: {fill.message}"
            body = self._decision_body(
                intent.ticker,
                intent.sim_day,
                intent.action,
                selection,
                proposal,
                news,
                reason,
                True,
                executed,
                None if executed else fill.message,
            )
            await self._remember_decision(body)
            order = self._order_row(
                intent,
                fill.status,
                fill.message,
                fill.brokerage,
                fill.taxes_and_fees,
                fill.order_id,
            )
            await self._remember_order(order)
            if publish:
                self.bus.publish({"type": "strategy.signal", "data": body})
                self.bus.publish({"type": "order.result", "data": order})
                self.bus.publish({"type": "portfolio.updated", "data": self.portfolio_view()})

    async def _fill(self, intent: OrderIntent) -> Fill:
        armed = self.settings.live_submission_armed()
        if self.settings.market_mode != "venue" or not armed:
            return self._mock_fill(intent)
        try:
            template = load_template(self.settings.venue_order_template_path)
            payload = render(
                template,
                {
                    "ticker": intent.ticker,
                    "action": intent.action,
                    "quantity": str(intent.quantity),
                    "price": f"{intent.price:.4f}",
                    "sim_day": str(intent.sim_day),
                    "client_order_id": intent.client_order_id,
                },
            )
            body = await self.client.post_order(payload)
        except ApiError as exc:
            status = "UNKNOWN" if exc.kind == "timeout" else "FAILED"
            return self._blank_fill(intent, status, str(exc), "venue")
        except (TemplateError, OSError) as exc:
            return self._blank_fill(intent, "FAILED", str(exc), "venue")
        field = self.settings.venue_order_status_field
        expected = self.settings.venue_order_status_value
        if field and isinstance(body, dict) and str(body.get(field)) == expected and expected:
            cost = quote_cost(self.settings, intent.quantity * intent.price)
            self.order_seq += 1
            return Fill(
                client_order_id=intent.client_order_id,
                order_id=f"venue-{self.order_seq}",
                ticker=intent.ticker,
                action=intent.action,
                quantity=intent.quantity,
                price=intent.price,
                sim_day=intent.sim_day,
                status="FILLED",
                brokerage=cost.brokerage,
                taxes_and_fees=cost.taxes_and_fees,
                message="Venue status matched the configured fill field. Local position is an estimate.",
                venue="venue",
                strategy=intent.strategy,
                signal_score=intent.signal_score,
                reason=intent.reason,
            )
        return self._blank_fill(
            intent,
            "UNKNOWN",
            "HTTP success but the fill status field is not configured or did not match. Not retried.",
            "venue",
        )

    def _mock_fill(self, intent: OrderIntent) -> Fill:
        cost = quote_cost(self.settings, intent.quantity * intent.price)
        self.order_seq += 1
        return Fill(
            client_order_id=intent.client_order_id,
            order_id=f"mock-{self.order_seq}",
            ticker=intent.ticker,
            action=intent.action,
            quantity=intent.quantity,
            price=intent.price,
            sim_day=intent.sim_day,
            status="FILLED",
            brokerage=cost.brokerage,
            taxes_and_fees=cost.taxes_and_fees,
            message="Dry-run fill at the simulated candle close on the local mock exchange.",
            venue="mock",
            strategy=intent.strategy,
            signal_score=intent.signal_score,
            reason=intent.reason,
        )

    def _blank_fill(self, intent: OrderIntent, status: str, message: str, venue: str) -> Fill:
        self.order_seq += 1
        return Fill(
            client_order_id=intent.client_order_id,
            order_id=f"{venue}-{self.order_seq}",
            ticker=intent.ticker,
            action=intent.action,
            quantity=intent.quantity,
            price=intent.price,
            sim_day=intent.sim_day,
            status=status,  # type: ignore[arg-type]
            message=message,
            venue=venue,
            strategy=intent.strategy,
            signal_score=intent.signal_score,
            reason=intent.reason,
        )

    def _risk_context(self) -> RiskContext:
        return RiskContext(
            stage=self.lifecycle.stage,
            heartbeat_fresh=self.lifecycle.fresh(time.monotonic())
            or (self.settings.replay_mode == "instant" and self.lifecycle.ack_count > 0),
            paused=self.paused,
            data_stale=self._stale(),
            portfolio_reliable=self.portfolio.reliable,
            rate_limit_ok=self.limiter.remaining() > 0 or self.settings.market_mode != "venue",
            live_armed=self.settings.live_submission_armed(),
            market_mode=self.settings.market_mode,
            marks=dict(self.marks),
            orders_today=self.orders_today.get(self.sim_day, 0),
            outstanding=self.outstanding,
            seen_order_ids=self.seen_order_ids,
            auth_ok=bool(self.settings.bot_access_token.strip()) or self.settings.market_mode != "venue",
        )

    def _stale(self) -> bool:
        if self.outage:
            return True
        if self.settings.replay_mode == "instant":
            return False
        if self.last_event_wall <= 0:
            return False
        limit = max(8.0, self.settings.sim_day_seconds * self.settings.stale_feed_multiplier)
        return (time.monotonic() - self.last_event_wall) > limit

    def _trend_label(self, snap) -> str:
        if snap.ema9 is not None and snap.ema21 is not None and snap.ema9 > snap.ema21:
            return "bullish"
        if snap.ema9 is not None and snap.ema21 is not None and snap.ema9 < snap.ema21:
            return "bearish"
        return "flat"

    def _decision_body(self, ticker, day, action, selection, proposal, news, reason, risk_approved, executed, rejection) -> dict:
        self.decision_seq += 1
        snap = self.snaps.get(ticker)
        indicators = {}
        if snap is not None:
            for key, value in snap.model_dump().items():
                indicators[key] = round(value, 4) if isinstance(value, float) else value
        return {
            "id": f"dec-{self.decision_seq}",
            "ticker": ticker,
            "action": action,
            "signal_score": round(selection.action_bias, 4),
            "score_type": "heuristic",
            "strategy": proposal.strategy,
            "selector": self.strategy_mode,
            "regime": selection.regime,
            "indicators": indicators,
            "contributions": selection.contributions,
            "risk_approved": risk_approved,
            "risk_reasons": [] if not rejection else [rejection],
            "executed": executed,
            "rejection_reason": rejection,
            "reason": reason,
            "timestamp": utcnow(),
            "sim_day": day,
            "news_label": None if news is None else news.label,
            "news_headline": None if news is None else news.headline,
        }

    def _order_row(self, intent: OrderIntent, status: str, message: str, brokerage: float, taxes: float, order_id: str) -> dict:
        return {
            "order_id": order_id,
            "client_order_id": intent.client_order_id,
            "ticker": intent.ticker,
            "action": intent.action,
            "quantity": intent.quantity,
            "price": _num(intent.price),
            "sim_day": intent.sim_day,
            "status": status,
            "message": message,
            "strategy": intent.strategy,
            "venue": "mock" if self.settings.market_mode != "venue" or not self.settings.live_submission_armed() else "venue",
            "brokerage": _num(brokerage),
            "taxes_and_fees": _num(taxes),
            "timestamp": utcnow(),
            "signal_score": round(intent.signal_score, 4),
        }

    async def _remember_decision(self, body: dict) -> None:
        self.decisions.append(body)
        if body["action"] != "HOLD" or body.get("rejection_reason"):
            self.trade_log.append(body)
        self._remember_audit("decision", body)
        if self.persist and body["action"] != "HOLD":
            await self._persist("decision", body)

    def decision_feed(self) -> list[dict]:
        rows = list(self.trade_log)
        for ticker in self.tickers:
            latest = self.latest_decision(ticker)
            if latest and latest["action"] == "HOLD":
                rows.append(latest)
        rows.sort(key=lambda item: int(str(item["id"]).split("-")[1]), reverse=True)
        return rows[:80]

    async def _remember_order(self, body: dict) -> None:
        self.orders.append(body)
        self._remember_audit("order", body)
        if self.persist:
            await self._persist("order", body)

    def _remember_audit(self, event_type: str, payload: dict) -> None:
        self.audit.append({"ts": payload.get("timestamp") or utcnow(), "event_type": event_type, "payload": payload})

    async def _persist(self, event_type: str, payload: dict) -> None:
        try:
            await self.store.add(payload.get("timestamp") or utcnow(), event_type, payload)
        except Exception:
            logger.exception("audit persist failed")

    def latest_decision(self, ticker: str) -> dict | None:
        for body in reversed(self.decisions):
            if body["ticker"] == ticker:
                return body
        return None

    def _candle_row(self, candle: Candle, snap) -> dict:
        return {
            "ticker": candle.ticker,
            "sim_day": candle.sim_day,
            "time": candle.ts_unix,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            "ema9": _num(snap.ema9, 4),
            "ema21": _num(snap.ema21, 4),
            "ema50": _num(snap.ema50, 4),
            "rsi14": _num(snap.rsi14, 2),
            "macd": _num(snap.macd, 4),
            "macd_signal": _num(snap.macd_signal, 4),
            "macd_hist": _num(snap.macd_hist, 4),
            "source": candle.source,
        }

    def _news_row(self, item) -> dict:
        return {
            "event_id": item.event_id,
            "ticker": item.ticker,
            "sim_day": item.sim_day,
            "headline": item.headline,
            "body": item.body,
            "sentiment": _num(item.sentiment, 4),
            "severity": _num(item.severity, 4),
            "label": item.label,
            "source": item.source,
        }

    def _publish_health(self) -> None:
        self.bus.publish({"type": "system.health", "data": self.health_view()})

    def trading_lamp(self) -> str:
        if self.paused:
            return "PAUSED"
        if self.lifecycle.stage == "PREFLIGHT":
            return "PREFLIGHT"
        if self.lifecycle.stage == "ENDED":
            return "ENDED"
        if self.lifecycle.stage != "TRADING":
            return "HALTED"
        if self.outage or not self.lifecycle.fresh(time.monotonic()):
            return "HALTED"
        return "LIVE"

    def mode_label(self) -> str:
        if self.settings.dry_run:
            return "DRY_RUN"
        if self.settings.live_submission_armed():
            return "LIVE_SIMULATION"
        return "LIVE_LOCKED"

    def health_view(self) -> dict[str, Any]:
        if not self.settings.kafka_enabled:
            kafka = "disabled"
        elif self.kafka_connected:
            kafka = "connected"
        else:
            kafka = "disconnected"
        if self.settings.market_mode == "mock":
            api = "not_contacted"
        elif self.api_reachable is True:
            api = "reachable"
        elif self.api_reachable is False:
            api = "unreachable"
        else:
            api = "unknown"
        return {
            "kafka": kafka,
            "kafka_lag": self.kafka_lag,
            "trading_api": api,
            "heartbeat": self.lifecycle.heartbeat_status,
            "heartbeat_acks": self.lifecycle.ack_count,
            "heartbeat_error": self.lifecycle.last_error,
            "stage": self.lifecycle.stage,
            "sim_day": self.sim_day,
            "active_strategy": self.strategy_mode,
            "last_primary_strategy": self._last_primary(),
            "mode": self.mode_label(),
            "lamp": self.trading_lamp(),
            "feed": "interrupted" if self.outage else self.feed_status,
            "data_origin": "synthetic" if self.settings.market_mode == "mock" else "venue",
            "paused": self.paused,
            "decision_latency_ms_p50": _num(self.latency.p50, 3),
            "decision_latency_ms_max": _num(self.latency.max, 3),
            "rate_limit": {
                "used": self.limiter.used(),
                "limit": self.limiter.limit,
                "remaining": self.limiter.remaining(),
                "note": "Mock mode does not call the venue, so this budget stays unused.",
            },
            "stale": self._stale(),
            "last_event_age_sec": None
            if self.last_event_wall <= 0
            else round(time.monotonic() - self.last_event_wall, 3),
            "dropped_duplicates": sum(tape.dropped_duplicate for tape in self.tapes.values()),
            "dropped_reorder": sum(tape.dropped_reorder for tape in self.tapes.values()),
            "gaps": sum(tape.gaps for tape in self.tapes.values()),
        }

    def _last_primary(self) -> str | None:
        if not self.decisions:
            return None
        return self.decisions[-1]["strategy"]

    def lifecycle_view(self) -> dict[str, Any]:
        return {
            "stage": self.lifecycle.stage,
            "heartbeat": self.lifecycle.heartbeat_status,
            "acks": self.lifecycle.ack_count,
            "error": self.lifecycle.last_error,
            "sim_day": self.sim_day,
            "lamp": self.trading_lamp(),
        }

    def portfolio_view(self) -> dict[str, Any]:
        marks = self.marks
        equity = self.portfolio.equity(marks)
        invested = self.portfolio.long_market_value(marks)
        gross = self.portfolio.gross_exposure(marks)
        unrealized = self.portfolio.unrealized(marks)
        start = self.portfolio.starting_capital
        closed = len(self.portfolio.closed)
        holdings = []
        for pos in self.portfolio.positions.values():
            mark = marks.get(pos.ticker, pos.avg_price)
            if pos.side == "long":
                market_value = pos.quantity * mark
                upnl = (mark - pos.avg_price) * pos.quantity
            else:
                market_value = pos.quantity * mark
                upnl = (pos.avg_price - mark) * pos.quantity
            holdings.append(
                {
                    "ticker": pos.ticker,
                    "name": self.names.get(pos.ticker, pos.ticker),
                    "side": pos.side,
                    "quantity": pos.quantity,
                    "avg_price": money(pos.avg_price),
                    "last": money(mark),
                    "market_value": money(market_value),
                    "unrealized_pnl": money(upnl),
                    "unrealized_pnl_pct": None if pos.avg_price == 0 else round(upnl / (pos.avg_price * pos.quantity) * 100, 2),
                    "exposure_pct": None if equity <= 0 else round(market_value / equity * 100, 2),
                    "opened_day": pos.opened_day,
                    "synthetic": self.settings.market_mode == "mock",
                }
            )
        holdings.sort(key=lambda row: row["ticker"])
        return {
            "starting_capital": money(start),
            "cash": money(self.portfolio.cash),
            "available_cash": money(self.portfolio.available_cash()),
            "locked_collateral": money(self.portfolio.locked_collateral),
            "buying_power": money(max(0.0, self.portfolio.available_cash() - self.settings.min_cash_reserve_pct * equity)),
            "invested": money(invested),
            "gross_exposure": money(gross),
            "short_exposure": money(self.portfolio.short_liability(marks)),
            "realized_gross": money(self.portfolio.realized_gross),
            "unrealized_pnl": money(unrealized),
            "fees": money(self.portfolio.fees_paid),
            "brokerage": money(self.portfolio.brokerage_paid),
            "taxes_and_fees": money(self.portfolio.taxes_paid),
            "net_pnl": money(equity - start),
            "equity": money(equity),
            "total_return_pct": 0.0 if start == 0 else round((equity - start) / start * 100, 3),
            "drawdown_pct": round(self.portfolio.drawdown(marks) * 100, 3),
            "max_drawdown_pct": round(self.portfolio.max_drawdown * 100, 3),
            "win_rate": None if closed == 0 else round(self.portfolio.win_rate() * 100, 2),
            "closed_trades": closed,
            "wins": self.portfolio.wins(),
            "losses": self.portfolio.losses(),
            "fills": len(self.portfolio.fills),
            "valuation": self.portfolio.valuation,
            "reliable": self.portfolio.reliable,
            "holdings": holdings,
            "equity_history": self.portfolio.equity_history[-400:],
            "costs": {
                "brokerage": money(self.portfolio.brokerage_paid),
                "taxes_and_fees": money(self.portfolio.taxes_paid),
                "model": self.settings.cost_model,
                "official": False,
            },
        }

    def ticker_rows(self) -> list[dict]:
        rows = []
        for ticker in self.tickers:
            tape = self.tapes[ticker]
            if not tape.candles:
                continue
            last = tape.candles[-1]
            prev = tape.candles[-2].close if len(tape.candles) > 1 else last.close
            change = last.close - prev
            signal = self.signals.get(ticker, {})
            rows.append(
                {
                    "ticker": ticker,
                    "name": self.names.get(ticker, ticker),
                    "synthetic": self.settings.market_mode == "mock",
                    "last": last.close,
                    "change": round(change, 2),
                    "change_pct": 0.0 if prev == 0 else round(change / prev * 100, 2),
                    "volume": last.volume,
                    "signal": signal.get("action", "HOLD"),
                    "signal_score": signal.get("signal_score", 0.0),
                    "trend": signal.get("trend", "flat"),
                    "regime": signal.get("regime", "warming"),
                    "strategy": signal.get("strategy"),
                    "sim_day": last.sim_day,
                }
            )
        return rows

    def news_rows(self) -> list[dict]:
        rows = []
        for item in self.news.items[-30:]:
            rows.append(self._news_row(annotate(item, max(self.sim_day, item.sim_day))))
        return list(reversed(rows))

    def risk_view(self) -> dict[str, Any]:
        book = self.portfolio_view()
        equity = book["equity"] or 1
        largest = None
        for row in book["holdings"]:
            pct = row["exposure_pct"] or 0
            if largest is None or pct > largest["exposure_pct"]:
                largest = {"ticker": row["ticker"], "exposure_pct": pct, "side": row["side"]}
        dd = book["drawdown_pct"]
        limit = self.settings.max_drawdown_pct * 100
        if self.paused or self.lifecycle.stage != "TRADING" or dd >= limit:
            health = "blocked"
        elif dd >= limit * 0.5 or self.rejections:
            health = "caution"
        else:
            health = "healthy"
        return {
            "health": health,
            "drawdown_pct": dd,
            "max_allowed_drawdown_pct": round(limit, 2),
            "max_observed_drawdown_pct": book["max_drawdown_pct"],
            "gross_exposure": book["gross_exposure"],
            "exposure_pct": round(book["gross_exposure"] / equity * 100, 2) if equity else 0,
            "cash": book["cash"],
            "available_cash": book["available_cash"],
            "cash_reserve_pct": round(book["available_cash"] / equity * 100, 2) if equity else 0,
            "min_cash_reserve_pct": round(self.settings.min_cash_reserve_pct * 100, 2),
            "largest_position": largest,
            "short_exposure": book["short_exposure"],
            "paused": self.paused,
            "limits": {
                "max_position_pct": self.settings.max_position_pct,
                "max_invested_pct": self.settings.max_invested_pct,
                "max_orders_per_day": self.settings.max_orders_per_day,
                "orders_today": self.orders_today.get(self.sim_day, 0),
            },
            "recent_rejections": list(self.rejections)[-12:],
        }

    def snapshot(self) -> dict[str, Any]:
        book = self.portfolio_view()
        return {
            "meta": {
                "project": "MANTHAN QUANT",
                "data_origin": "synthetic" if self.settings.market_mode == "mock" else "venue",
                "disclaimer": (
                    "Synthetic demonstration tape. Figures come from the local mock exchange. "
                    "They are not live competition results."
                    if self.settings.market_mode == "mock"
                    else "Venue mode. Order payloads are sent only when an official template is configured."
                ),
                "cost_model": self.settings.cost_model,
                "cost_model_official": False,
                "dry_run": self.settings.dry_run,
                "trading_enabled": self.settings.trading_enabled,
                "live_submission_armed": self.settings.live_submission_armed(),
                "time_origin_unix": SYNTHETIC_EPOCH,
                "seconds_per_sim_day": self.settings.sim_day_seconds,
                "missing_official_docs": [
                    "Hackathon_Problem_Statement.pdf",
                    "Beginners_Guide_to_Trading_and_Investment.pdf",
                    "portal JSON schemas for the nine documented endpoints",
                    "bot authentication transport (portal console uses a cookie; bot mechanism is unresolved)",
                ],
                "initial_capital": self.settings.initial_capital,
            },
            "health": self.health_view(),
            "lifecycle": self.lifecycle_view(),
            "portfolio": book,
            "tickers": self.ticker_rows(),
            "decisions": self.decision_feed(),
            "orders": list(reversed(self.orders))[:80],
            "risk": self.risk_view(),
            "audit": list(reversed(self.audit))[:120],
            "milestones": dict(self.milestones),
            "news": self.news_rows(),
            "portal": local_portal_panel(
                sim_day=self.sim_day,
                total_days=self.dataset.days if self.dataset is not None else self.settings.synthetic_days,
                interval_seconds=self.settings.sim_day_seconds,
                cash=book["cash"],
            ),
        }

    def candles(self, ticker: str) -> list[dict]:
        return list(self.enriched.get(ticker, []))

    def filtered_audit(self, ticker: str = "", action: str = "", status: str = "", sim_day: str = "", q: str = "") -> list[dict]:
        rows = []
        for item in reversed(self.audit):
            payload = item["payload"]
            if ticker and payload.get("ticker") != ticker:
                continue
            if action and payload.get("action") != action:
                continue
            if status and payload.get("status") != status and payload.get("action") != status:
                continue
            if sim_day != "" and str(payload.get("sim_day")) != str(sim_day):
                continue
            if q and q.lower() not in json_blob(payload):
                continue
            rows.append(item)
            if len(rows) >= 200:
                break
        return rows

    async def pause(self) -> dict:
        self.paused = True
        self._publish_health()
        body = {"ok": True, "paused": True, "ack": True, "lamp": self.trading_lamp()}
        self.bus.publish({"type": "system.health", "data": self.health_view()})
        return body

    async def resume(self) -> dict:
        self.paused = False
        body = {"ok": True, "paused": False, "ack": True, "lamp": self.trading_lamp()}
        self._publish_health()
        return body

    def schedule_outage(self, seconds: float) -> dict:
        if self.settings.market_mode != "mock":
            return {"ok": False, "error": "outage simulation is only available in mock mode"}
        seconds = max(1.0, min(seconds, 30.0))
        asyncio.create_task(self._outage(seconds))
        return {"ok": True, "ack": True, "started": True, "seconds": seconds}

    async def _outage(self, seconds: float) -> None:
        previous = self.feed_status
        self.outage = True
        self.feed_status = "interrupted"
        self._publish_health()
        await self._sleep(seconds)
        self.outage = False
        if self.lifecycle.stage == "TRADING":
            self.feed_status = "live"
        elif previous not in {"", "interrupted"}:
            self.feed_status = previous
        else:
            self.feed_status = "ended" if self.lifecycle.stage == "ENDED" else "live"
        self.milestones["outage_recovered"] = True
        self.last_event_wall = time.monotonic()
        self._publish_health()
        self._remember_audit("feed_recovered", {"timestamp": utcnow(), "seconds": seconds})

    async def probe_venue(self) -> dict:
        try:
            raw = await self.client.get_stage()
            self.api_reachable = True
            return {
                "reachable": True,
                "schema_recognized": isinstance(raw, dict),
                "error": "",
            }
        except Exception as exc:  # noqa: BLE001 - probe reports the class, not a stack
            self.api_reachable = False
            return {"reachable": False, "schema_recognized": False, "error": exc.__class__.__name__}


def json_blob(payload: dict) -> str:
    parts = [str(payload.get("ticker", "")), str(payload.get("action", "")), str(payload.get("reason", "")), str(payload.get("message", ""))]
    return " ".join(parts).lower()
