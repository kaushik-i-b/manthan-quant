"""Per-ticker candle book with duplicate and out-of-order handling."""

from __future__ import annotations

from app.models.types import Candle, NewsItem


class TickerTape:
    def __init__(self) -> None:
        self.candles: list[Candle] = []
        self.ids: set[str] = set()
        self.last_day = -1
        self.dropped_duplicate = 0
        self.dropped_reorder = 0
        self.gaps = 0

    def add(self, candle: Candle) -> bool:
        if candle.event_id in self.ids:
            self.dropped_duplicate += 1
            return False
        if candle.sim_day <= self.last_day:
            self.ids.add(candle.event_id)
            self.dropped_reorder += 1
            return False
        if self.last_day >= 0 and candle.sim_day > self.last_day + 1:
            self.gaps += 1
        self.ids.add(candle.event_id)
        self.last_day = candle.sim_day
        self.candles.append(candle)
        return True


class NewsTape:
    def __init__(self) -> None:
        self.items: list[NewsItem] = []
        self.ids: set[str] = set()
        self.dropped_duplicate = 0

    def add(self, item: NewsItem) -> bool:
        if item.event_id in self.ids:
            self.dropped_duplicate += 1
            return False
        self.ids.add(item.event_id)
        self.items.append(item)
        return True

    def latest(self, ticker: str, day: int, max_age: int = 1) -> NewsItem | None:
        fresh = [
            item
            for item in self.items
            if item.ticker == ticker and 0 <= day - item.sim_day <= max_age
        ]
        if not fresh:
            return None
        return max(fresh, key=lambda item: (item.sim_day, item.severity or 0))
