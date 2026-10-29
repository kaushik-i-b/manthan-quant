"""MANTHAN QUANT backend: FastAPI + engine loop + WebSocket streaming."""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.backtesting.engine import run_backtest
from app.config import settings
from app.execution.api_client import ApiClient
from app.execution.executor import Executor
from app.execution.lifecycle import Lifecycle
from app.indicators.engine import IndicatorEngine
from app.market.bus import Bus
from app.market.ingestion import Ingestion
from app.models.schemas import Action, SimStage
from app.portfolio.manager import Portfolio
from app.risk.engine import RiskEngine
from app.sentiment.analyzer import classify
from app.simulation.mock_exchange import MockExchange, SYMBOLS
from app.strategies import engine as strat
from app.strategies.engine import Ctx

bus = Bus()
api = ApiClient()
lifecycle = Lifecycle(api)
portfolio = Portfolio()
risk = RiskEngine()
indicators = IndicatorEngine()
mock = MockExchange(seed=42)
executor = Executor(api, risk, portfolio)

prices: dict[str, float] = dict.fromkeys(SYMBOLS, 0.0)
latest_ind: dict[str, dict] = {}
latest_news: dict[str, dict] = {}
news_fresh: dict[str, dict] = {}
signals_log: list[dict] = []
t0 = time.time()
decisions = {"count": 0, "latency_ms": []}


async def broadcast(etype: str, payload: dict) -> None:
    await bus.publish(etype, payload)


async def handle_tick(data: dict) -> None:
    t_start = time.perf_counter()
    tk = data["ticker"]
    prices[tk] = data["close"]
    snap = indicators.on_candle(tk, data["open"], data["high"], data["low"], data["close"], data["volume"])
    latest_ind[tk] = snap
    lifecycle.sim_day = max(lifecycle.sim_day, data.get("sim_day", 0))
    await bus.publish("market.tick", data)
    # strategy evaluation (bounded, non-blocking: one ticker per tick)
    nf = news_fresh.get(tk)
    fresh = bool(nf and (lifecycle.sim_day - nf.get("sim_day", -99)) <= 2)
    ctx = Ctx(ticker=tk, ind=snap, sentiment=(nf or {}).get("sentiment", "neutral"),
              severity=(nf or {}).get("severity", 0.0), news_fresh=fresh, sim_day=lifecycle.sim_day)
    bars = mock.history.get(tk, [])
    hi = max((b["high"] for b in bars[-20:]), default=None)
    lo = min((b["low"] for b in bars[-20:]), default=None)
    votes = [strat.trend_strategy(ctx), strat.mean_reversion_strategy(ctx),
             strat.breakout_strategy(ctx, hi, lo), strat.news_strategy(ctx)]
    regime = strat.classify_regime(snap, fresh, ctx.sentiment)
    sig = strat.combine(votes, regime)
    sig.sim_day = lifecycle.sim_day
    signals_log.append(sig.model_dump(mode="json"))
    if len(signals_log) > 500:
        signals_log.pop(0)
    decisions["count"] += 1
    decisions["latency_ms"].append((time.perf_counter() - t_start) * 1000)
    if len(decisions["latency_ms"]) > 200:
        decisions["latency_ms"] = decisions["latency_ms"][-200:]
    executor.sim_active = lifecycle.trading_active
    if lifecycle.trading_active and settings.TRADING_ENABLED:
        try:
            executor.queue.put_nowait(sig)
        except asyncio.QueueFull:
            pass
    else:
        # still emit signal for dashboard even when order submission disabled
        await bus.publish("strategy.signal", sig.model_dump(mode="json"))
        await bus.publish("portfolio.updated", portfolio.snapshot(prices, lifecycle.sim_day).model_dump(mode="json"))


async def handle_news(data: dict) -> None:
    sent, sev = classify(data.get("headline", ""), data.get("body", ""))
    data = {**data, "sentiment": sent, "severity": round(sev, 3)}
    latest_news[data.get("ticker", "?")] = data
    news_fresh[data.get("ticker", "?")] = data
    await bus.publish("market.news", data)


ingestion = Ingestion(bus, handle_tick, handle_news)


async def mock_loop() -> None:
    """Local simulated market: ticks every SIM_TICK_INTERVAL_SEC, news ~150ms after."""
    # warm indicators with history
    for s in SYMBOLS:
        for b in mock.get_history(s):
            prices[s] = b["close"]
            latest_ind[s] = indicators.on_candle(s, b["open"], b["high"], b["low"], b["close"], b["volume"])
    while True:
        await asyncio.sleep(settings.SIM_TICK_INTERVAL_SEC)
        if lifecycle.stage == SimStage.ENDED:
            continue
        for tick in mock.next_ticks():
            await handle_tick(tick)
        await asyncio.sleep(0.15)
        for n in mock.maybe_news():
            await handle_news(n)
        await bus.publish("system.health", health_payload())
        await bus.publish("simulation.stage", {"stage": lifecycle.stage.value, "sim_day": lifecycle.sim_day})


def health_payload() -> dict:
    lat = decisions["latency_ms"]
    return {
        "kafka": ingestion.mode, "kafka_connected": ingestion.connected,
        "api_ok": api.ok, "api_latency_ms": api.avg_latency_ms,
        "rate_used": api.limiter.usage, "rate_limit": settings.API_RATE_LIMIT_PER_MIN,
        "heartbeat_ok": lifecycle.hb_ok, "heartbeat_fails": lifecycle.hb_fails,
        "stage": lifecycle.stage.value, "sim_day": lifecycle.sim_day,
        "dry_run": settings.DRY_RUN, "trading_enabled": settings.TRADING_ENABLED,
        "decisions": decisions["count"],
        "avg_decision_ms": round(sum(lat) / len(lat), 2) if lat else 0,
        "uptime_s": round(time.time() - t0, 1),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(mock_loop()),
             asyncio.create_task(ingestion.run()),
             asyncio.create_task(lifecycle.heartbeat_loop()),
             asyncio.create_task(executor.run_forever(prices, broadcast))]
    yield
    for tk in tasks:
        tk.cancel()

app = FastAPI(title="MANTHAN QUANT", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health(): return health_payload()

@app.get("/api/stocks")
def stocks():
    return [{"ticker": s, "price": prices.get(s, 0), "indicators": latest_ind.get(s, {}),
             "news": latest_news.get(s)} for s in SYMBOLS]

@app.get("/api/stocks/{ticker}/history")
def history(ticker: str, n: int = 120):
    return mock.get_history(ticker.upper(), n)

@app.get("/api/portfolio")
def get_portfolio():
    return portfolio.snapshot(prices, lifecycle.sim_day).model_dump(mode="json")

@app.get("/api/signals")
def signals(n: int = 50): return signals_log[-n:][::-1]

@app.get("/api/orders")
def orders(): return list(executor.orders)[::-1]

@app.get("/api/events")
def events(n: int = 100): return bus.recent(n)

@app.get("/api/risk")
def risk_state():
    eq = portfolio.equity(prices)
    snap = portfolio.snapshot(prices, lifecycle.sim_day)
    return {"paused": risk.paused, "pause_reason": risk.pause_reason,
            "max_drawdown_pct": settings.MAX_DRAWDOWN_PCT * 100,
            "current_drawdown_pct": snap.drawdown_pct,
            "exposure_pct": round(snap.invested / max(eq, 1) * 100, 2),
            "cash_reserve_pct": round(snap.cash / max(eq, 1) * 100, 2),
            "min_cash_pct": settings.MIN_CASH_RESERVE_PCT * 100,
            "orders_today": risk.orders_today, "max_orders_day": settings.MAX_ORDERS_PER_DAY,
            "violations": risk.violations[-20:],
            "limits": {"max_position_pct": settings.MAX_POSITION_PCT * 100,
                       "max_concentration_pct": settings.MAX_CONCENTRATION_PCT * 100,
                       "max_invested_pct": settings.MAX_INVESTED_PCT * 100}}

class PauseCmd(BaseModel):
    paused: bool
    reason: str = ""

@app.post("/api/risk/pause")
def pause(cmd: PauseCmd):
    risk.set_paused(cmd.paused, cmd.reason)
    return {"paused": risk.paused}

class BacktestReq(BaseModel):
    strategy: str = "adaptive"
    seed: int = 42

@app.post("/api/backtest")
def backtest(req: BacktestReq):
    from app.simulation.mock_exchange import MockExchange as ME
    me = ME(seed=req.seed)
    data = {s: me.history[s][-120:] for s in SYMBOLS[:6]}
    out = {}
    for st in ([req.strategy] if req.strategy != "all" else ["adaptive", "trend", "meanrev", "breakout"]):
        out[st] = run_backtest(data, st)
        out[st].pop("equity_curve", None)
    # buy&hold baseline
    first = {s: data[s][0]["close"] for s in data}
    last = {s: data[s][-1]["close"] for s in data}
    bh = sum(last[s] / first[s] for s in data) / len(data)
    out["buy_hold_baseline_pct"] = round((bh - 1) * 100, 2)
    out["note"] = "Backend backtest on deterministic synthetic candles (seed=%d). Labeled synthetic." % req.seed
    return out

@app.post("/api/demo/reset")
def demo_reset():
    mock.reset(42)
    portfolio.reset()
    signals_log.clear()
    lifecycle.sim_day = 0
    return {"ok": True}

@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    q = bus.subscribe()
    # initial snapshot
    await ws.send_json({"type": "portfolio.updated", "payload": portfolio.snapshot(prices, lifecycle.sim_day).model_dump(mode="json")})
    try:
        while True:
            msg = await q.get()
            await ws.send_json(msg)
    except WebSocketDisconnect:
        pass
