"""Bounded latency samples. Percentiles are computed from measured values only."""

from __future__ import annotations

from collections import deque


class LatencyTracker:
    def __init__(self, maxlen: int = 400) -> None:
        self.samples: deque[float] = deque(maxlen=maxlen)

    def add(self, milliseconds: float) -> None:
        self.samples.append(float(milliseconds))

    def percentile(self, pct: float) -> float | None:
        if not self.samples:
            return None
        ordered = sorted(self.samples)
        if len(ordered) == 1:
            return ordered[0]
        rank = (len(ordered) - 1) * pct
        low = int(rank)
        high = min(low + 1, len(ordered) - 1)
        weight = rank - low
        return ordered[low] * (1 - weight) + ordered[high] * weight

    @property
    def p50(self) -> float | None:
        return self.percentile(0.50)

    @property
    def max(self) -> float | None:
        if not self.samples:
            return None
        return max(self.samples)
