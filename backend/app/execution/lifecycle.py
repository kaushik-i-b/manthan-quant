"""Lifecycle manager: stage detection + heartbeat loop, independent of analytics."""
from __future__ import annotations

import asyncio
import time

from app.config import settings
from app.execution.api_client import ApiClient
from app.models.schemas import SimStage


class Lifecycle:
    def __init__(self, api: ApiClient) -> None:
        self.api = api
        self.stage: SimStage = SimStage.PRE_FLIGHT if not settings.MOCK_MODE else SimStage.TRADING
        self.sim_day = 0
        self.hb_ok = True
        self.hb_last: float | None = None
        self.hb_fails = 0
        self.log: list[dict] = []

    async def heartbeat_loop(self) -> None:
        while True:
            try:
                r = await self.api.heartbeat()
                self.hb_ok = bool(r.get("ok"))
                self.hb_last = time.time()
                if not self.hb_ok:
                    self.hb_fails += 1
                else:
                    if self.stage == SimStage.PRE_FLIGHT:
                        self.stage = SimStage.TRADING
            except Exception:
                self.hb_ok = False
                self.hb_fails += 1
            await asyncio.sleep(settings.HEARTBEAT_INTERVAL_SEC)

    def set_stage(self, stage: SimStage) -> None:
        self.stage = stage
        self.log.append({"stage": stage.value})

    @property
    def trading_active(self) -> bool:
        return self.stage == SimStage.TRADING and (settings.MOCK_MODE or self.hb_ok)
