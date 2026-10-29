"""Read models for the desk, plus authenticated local controls.

Pause, resume, and the outage drill do not submit venue orders.
"""

from __future__ import annotations

import asyncio
import hmac

from fastapi import APIRouter, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.backtesting.engine import compare_strategies
from app.runtime import TradingRuntime

router = APIRouter()


def _runtime(request: Request) -> TradingRuntime:
    return request.app.state.runtime


def _check_control(runtime: TradingRuntime, authorization: str | None) -> None:
    header = authorization or ""
    prefix = "Bearer "
    if not header.startswith(prefix):
        raise HTTPException(status_code=401, detail="control token required")
    token = header[len(prefix) :].strip()
    if not hmac.compare_digest(token, runtime.settings.control_token):
        raise HTTPException(status_code=401, detail="control token rejected")


class OutageBody(BaseModel):
    seconds: float = Field(default=6, ge=1, le=30)


@router.get("/health")
async def health(request: Request) -> dict:
    runtime = _runtime(request)
    return {"ok": True, "health": runtime.health_view(), "milestones": runtime.milestones}


@router.get("/snapshot")
async def snapshot(request: Request) -> dict:
    return _runtime(request).snapshot()


@router.get("/candles/{ticker}")
async def candles(ticker: str, request: Request) -> dict:
    runtime = _runtime(request)
    rows = runtime.candles(ticker)
    if not rows and ticker not in runtime.tapes:
        raise HTTPException(status_code=404, detail="unknown ticker")
    return {"ticker": ticker, "candles": rows, "source": "synthetic" if runtime.settings.market_mode == "mock" else "venue"}


@router.get("/audit")
async def audit(
    request: Request,
    ticker: str = "",
    action: str = "",
    status: str = "",
    sim_day: str = "",
    q: str = "",
) -> dict:
    return {"rows": _runtime(request).filtered_audit(ticker, action, status, sim_day, q)}


@router.post("/control/pause")
async def pause(request: Request, authorization: str | None = Header(default=None)) -> dict:
    runtime = _runtime(request)
    _check_control(runtime, authorization)
    return await runtime.pause()


@router.post("/control/resume")
async def resume(request: Request, authorization: str | None = Header(default=None)) -> dict:
    runtime = _runtime(request)
    _check_control(runtime, authorization)
    return await runtime.resume()


@router.post("/demo/outage")
async def outage(
    body: OutageBody,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    runtime = _runtime(request)
    _check_control(runtime, authorization)
    return runtime.schedule_outage(body.seconds)


@router.post("/venue/probe")
async def probe(request: Request, authorization: str | None = Header(default=None)) -> dict:
    runtime = _runtime(request)
    _check_control(runtime, authorization)
    return await runtime.probe_venue()


def _compare_blocking(settings) -> dict:
    """Run the replay on a worker thread so the live tape keeps its event loop."""
    return asyncio.run(compare_strategies(settings))


@router.post("/backtest/compare")
async def backtest(request: Request) -> dict:
    runtime = _runtime(request)
    return await asyncio.to_thread(_compare_blocking, runtime.settings)


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    runtime: TradingRuntime = websocket.app.state.runtime
    queue = runtime.bus.subscribe()
    try:
        await websocket.send_json({"type": "snapshot", "data": runtime.snapshot()})
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        runtime.bus.unsubscribe(queue)
