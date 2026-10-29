"""Contract-aware venue client.

Read and write calls require a verified portal catalog. Order submission is
not retried. This client is not used by the dry-run simulator.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.api.auth import bearer_headers
from app.api.errors import ApiError, SchemaNotConfigured
from app.api.models import ContractCatalog, EndpointSpec, serialize_body
from app.config import Settings
from app.execution.rate_limit import RateLimiter
from app.logging_setup import log

logger = logging.getLogger("manthan.contracts")


class ContractClient:
    def __init__(
        self,
        settings: Settings,
        catalog: ContractCatalog,
        limiter: RateLimiter | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        allow_unofficial: bool = False,
    ) -> None:
        self.settings = settings
        self.catalog = catalog
        self.allow_unofficial = allow_unofficial
        self.limiter = limiter or RateLimiter(settings.api_rate_limit_per_min)
        self._client = httpx.AsyncClient(
            base_url=settings.trading_api_url.rstrip("/"),
            timeout=httpx.Timeout(settings.api_timeout_sec),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _endpoint(self, method: str, path: str) -> EndpointSpec:
        found = self.catalog.endpoint(method, path)
        if found is None or found.status != "verified":
            raise SchemaNotConfigured(f"no verified contract for {method} {path}")
        return found

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        idempotent: bool,
    ) -> Any:
        self._endpoint(method, path)
        delay = 0.05
        attempt = 0
        while True:
            if not self.limiter.try_acquire():
                raise ApiError("rate_limit", "local request budget exhausted")
            request_id = uuid.uuid4().hex
            headers = bearer_headers(self.settings.bot_access_token)
            headers["X-Request-ID"] = request_id
            log(logger, logging.INFO, "contract request", method=method, path=path, request_id=request_id)
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
            if not response.content:
                return {}
            return response.json()

    async def get_json(self, path: str) -> Any:
        return await self.request("GET", path, idempotent=True)

    async def submit(self, method: str, path: str, values: dict[str, Any]) -> Any:
        endpoint = self._endpoint(method, path)
        if method.upper() == "POST" and path.rstrip("/").endswith("/orders"):
            if self.settings.dry_run or not self.settings.trading_enabled:
                raise SchemaNotConfigured("order submission is disabled while DRY_RUN or TRADING_ENABLED is off")
        body = serialize_body(endpoint, values, catalog=self.catalog, allow_unofficial=self.allow_unofficial)
        idempotent = not (method.upper() == "POST" and "order" in path)
        return await self.request(method, path, json_body=body, idempotent=idempotent)
