"""Async venue API client with rate limiting, retries, audit. Mock-backed by default."""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque

import httpx

from app.config import settings


class RateLimiter:
    def __init__(self, per_min: int) -> None:
        self.per_min = per_min
        self.calls: deque[float] = deque()

    async def acquire(self) -> None:
        now = time.monotonic()
        while self.calls and now - self.calls[0] > 60:
            self.calls.popleft()
        if len(self.calls) >= self.per_min:
            await asyncio.sleep(60 - (now - self.calls[0]) + 0.05)
        self.calls.append(time.monotonic())

    @property
    def usage(self) -> int:
        now = time.monotonic()
        while self.calls and now - self.calls[0] > 60:
            self.calls.popleft()
        return len(self.calls)


class ApiClient:
    def __init__(self) -> None:
        self.limiter = RateLimiter(settings.API_RATE_LIMIT_PER_MIN)
        self.latencies: deque[float] = deque(maxlen=100)
        self.errors = 0
        self.ok = True
        self._client: httpx.AsyncClient | None = None

    async def _client_get(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=settings.TRADING_API_URL,
                                             timeout=httpx.Timeout(5.0, connect=3.0),
                                             headers={"Authorization": f"Bearer {settings.BOT_ACCESS_TOKEN}"} if settings.BOT_ACCESS_TOKEN else {})
        return self._client

    async def heartbeat(self) -> dict:
        """POST /bot/heartbeat per spec. Mock ack in MOCK_MODE."""
        if settings.MOCK_MODE or not settings.BOT_ACCESS_TOKEN:
            return {"ok": True, "mock": True, "stage": "TRADING"}
        await self.limiter.acquire()
        t0 = time.monotonic()
        try:
            c = await self._client_get()
            r = await c.post("/bot/heartbeat", json={"ack": True, "correlationId": uuid.uuid4().hex})
            self.latencies.append((time.monotonic() - t0) * 1000)
            self.ok = r.status_code < 500
            return {"ok": self.ok, "status": r.status_code, "body": r.text[:500]}
        except Exception as e:  # network down (venue wifi)
            self.errors += 1
            self.ok = False
            return {"ok": False, "error": str(e)[:300]}

    async def get_stage(self) -> dict:
        if settings.MOCK_MODE or not settings.BOT_ACCESS_TOKEN:
            return {"ok": True, "mock": True, "stage": "TRADING"}
        await self.limiter.acquire()
        try:
            c = await self._client_get()
            r = await c.get("/stage")
            return {"ok": r.status_code == 200, "status": r.status_code, "body": r.text[:500]}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    async def submit_order(self, payload: dict) -> dict:
        """Venue order submission. In DRY_RUN/MOCK returns simulated ack without network."""
        if settings.MOCK_MODE or settings.DRY_RUN or not settings.BOT_ACCESS_TOKEN:
            await asyncio.sleep(0.01)
            return {"ok": True, "mock": True, "orderId": f"mock-{uuid.uuid4().hex[:8]}", "echo": payload}
        await self.limiter.acquire()
        t0 = time.monotonic()
        retries = 0
        while True:
            try:
                c = await self._client_get()
                r = await c.post("/orders", json=payload)
                self.latencies.append((time.monotonic() - t0) * 1000)
                if r.status_code in (429,) and retries < 3:
                    retries += 1
                    await asyncio.sleep(2 ** retries)
                    continue
                return {"ok": r.status_code < 300, "status": r.status_code, "body": r.text[:1000]}
            except Exception as e:
                if retries < 3:
                    retries += 1
                    await asyncio.sleep(2 ** retries)
                    continue
                self.errors += 1
                return {"ok": False, "error": str(e)[:300]}

    @property
    def avg_latency_ms(self) -> float:
        return round(sum(self.latencies) / len(self.latencies), 1) if self.latencies else 0.0
