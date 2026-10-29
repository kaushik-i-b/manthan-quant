"""In-process fan-out. The trading path does not depend on a subscriber."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any


class EventBus:
    def __init__(self, max_buffer: int = 400) -> None:
        self.max_buffer = max_buffer
        self._queues: list[asyncio.Queue] = []
        self.recent: deque[dict[str, Any]] = deque(maxlen=max_buffer)
        self.published = 0

    def subscribe(self, maxsize: int = 400) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._queues.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._queues:
            self._queues.remove(queue)

    def publish(self, event: dict[str, Any]) -> None:
        self.published += 1
        self.recent.append(event)
        for queue in list(self._queues):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue
