"""Fan-out event bus + WebSocket broadcaster registry."""
from __future__ import annotations

import asyncio
import time
from collections import deque


class Bus:
    def __init__(self) -> None:
        self.subs: list[asyncio.Queue] = []
        self.event_log: deque[dict] = deque(maxlen=500)
        self.counts: dict[str, int] = {}
        self.last_event_ts: float | None = None

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.subs.append(q)
        return q

    async def publish(self, etype: str, payload: dict) -> None:
        msg = {"type": etype, "payload": payload, "server_ts": time.time()}
        self.event_log.appendleft(msg)
        self.counts[etype] = self.counts.get(etype, 0) + 1
        self.last_event_ts = time.time()
        for q in list(self.subs):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def recent(self, n: int = 100) -> list[dict]:
        return list(self.event_log)[:n]
