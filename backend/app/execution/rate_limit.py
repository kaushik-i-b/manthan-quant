"""Process-local request budget. The competition limit is 120 requests/minute."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        limit: int = 120,
        window_sec: float = 60.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if limit < 1:
            raise ValueError("limit must be positive")
        self.limit = limit
        self.window_sec = window_sec
        self.clock = clock or time.monotonic
        self._hits: deque[float] = deque()

    def _trim(self, now: float) -> None:
        while self._hits and now - self._hits[0] >= self.window_sec:
            self._hits.popleft()

    def try_acquire(self) -> bool:
        now = self.clock()
        self._trim(now)
        if len(self._hits) >= self.limit:
            return False
        self._hits.append(now)
        return True

    def used(self) -> int:
        self._trim(self.clock())
        return len(self._hits)

    def remaining(self) -> int:
        return max(0, self.limit - self.used())
