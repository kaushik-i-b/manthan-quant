"""Async venue client.

GET requests may retry with exponential backoff. Order POSTs are never
retried: a timeout becomes UNKNOWN and the ticker is frozen until a human
reconciles it. Payloads are supplied by the caller. This client does not
invent an order or heartbeat body.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.config import Settings
from app.execution.rate_limit import RateLimiter
from app.logging_setup import log

logger = logging.getLogger("manthan.api")


class ApiError(Exception):
    def __init__(self, kind: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


class SchemaNotConfigured(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__("schema", message)


class TradingApiClient:
    def __init__(
        self,
        settings: Settings,
        limiter: RateLimiter,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.limiter = limiter
        self.calls = 0
        self._client = httpx.AsyncClient(
            base_url=settings.trading_api_url.rstrip("/"),
            timeout=httpx.Timeout(settings.api_timeout_sec),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"X-Request-ID": uuid.uuid4().hex, "Accept": "application/json"}
        token = self.settings.bot_access_token.strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        idempotent: bool,
    ) -> httpx.Response:
        delay = 0.05
        attempt = 0
        while True:
            if not self.limiter.try_acquire():
                raise ApiError("rate_limit", "local 120/minute budget exhausted")
            self.calls += 1
            request_id = uuid.uuid4().hex
            headers = self._headers()
            headers["X-Request-ID"] = request_id
            log(
                logger,
                logging.INFO,
                "venue request",
                method=method,
                path=path,
                request_id=request_id,
                attempt=attempt,
            )
            try:
                response = await self._client.request(method, path, json=json_body, headers=headers)
            except httpx.TimeoutException as exc:
                if idempotent and attempt < 2:
                    attempt += 1
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise ApiError("timeout", "venue timeout") from exc
            except httpx.HTTPError as exc:
                if idempotent and attempt < 2:
                    attempt += 1
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise ApiError("network", "venue network error") from exc

            if response.status_code == 401:
                raise ApiError("auth", "venue rejected the bearer token", 401)
            if response.status_code == 429 or response.status_code >= 500:
                if idempotent and attempt < 2:
                    attempt += 1
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise ApiError("http", f"venue status {response.status_code}", response.status_code)
            if response.status_code >= 400:
                raise ApiError("http", f"venue status {response.status_code}", response.status_code)
            return response

    async def get_stocks(self) -> Any:
        response = await self.request("GET", "/stocks", idempotent=True)
        return response.json()

    async def get_history(self, ticker: str) -> Any:
        response = await self.request("GET", f"/stocks/{ticker}/history", idempotent=True)
        return response.json()

    async def get_stage(self) -> Any:
        response = await self.request("GET", "/stage", idempotent=True)
        return response.json()

    async def post_heartbeat(self, payload: dict) -> Any:
        response = await self.request("POST", "/bot/heartbeat", json_body=payload, idempotent=True)
        if not response.content:
            return {}
        return response.json()

    async def post_order(self, payload: dict) -> Any:
        # Orders are not idempotent unless the venue documents an id. Do not retry.
        response = await self.request("POST", "/orders", json_body=payload, idempotent=False)
        if not response.content:
            return {}
        return response.json()
