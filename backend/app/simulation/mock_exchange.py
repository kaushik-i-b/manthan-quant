"""Deterministic mock exchange: generates ticks + news, executes at close price."""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone

SYMBOLS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "TATAMOTORS", "ITC", "LT", "AXISBANK"]
BASE = {"RELIANCE": 2450.0, "TCS": 3900.0, "HDFCBANK": 1620.0, "INFY": 1480.0, "ICICIBANK": 1120.0,
        "SBIN": 780.0, "TATAMOTORS": 960.0, "ITC": 470.0, "LT": 3520.0, "AXISBANK": 1180.0}

NEWS_POOL = [
    ("{t} reports record quarterly profit, beats estimates", "positive"),
    ("{t} announces capacity expansion and new deal wins", "positive"),
    ("Brokerage upgrades {t} on strong growth outlook", "positive"),
    ("{t} misses earnings, guides lower margins", "negative"),
    ("Regulator probes {t} over disclosure lapses", "negative"),
    ("{t} faces downgrade on weak demand signals", "negative"),
    ("{t} board approves dividend, steady outlook", "neutral"),
    ("{t} holds analyst meet, maintains guidance", "neutral"),
]


class MockExchange:
    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)
        self.sim_day = 0
        self.prices = dict(BASE)
        self.history: dict[str, list[dict]] = {s: [] for s in SYMBOLS}
        # warm-up 60 bars of history per symbol
        for _ in range(60):
            self._step(prime=True)

    def _step(self, prime: bool = False) -> list[dict]:
        ticks = []
        for s in SYMBOLS:
            drift = self.rng.gauss(0.0008, 0.012)
            # regime wave so trends/mean-reversion both appear
            wave = 0.004 * math.sin(self.sim_day / 9.0 + hash(s) % 7)
            o = self.prices[s]
            c = max(o * (1 + drift + wave), 1.0)
            h = max(o, c) * (1 + abs(self.rng.gauss(0, 0.003)))
            l = min(o, c) * (1 - abs(self.rng.gauss(0, 0.003)))
            v = int(self.rng.gauss(800_000, 300_000))
            v = max(50_000, v)
            # occasional volume spike
            if self.rng.random() < 0.04:
                v *= 3
            self.prices[s] = c
            t = {"ticker": s, "price": round(c, 2), "open": round(o, 2), "high": round(h, 2),
                 "low": round(l, 2), "close": round(c, 2), "volume": v, "sim_day": self.sim_day,
                 "ts": datetime.now(timezone.utc).isoformat()}
            self.history[s].append(t)
            if not prime:
                ticks.append(t)
        if not prime:
            self.sim_day += 1
        return ticks

    def next_ticks(self) -> list[dict]:
        return self._step()

    def maybe_news(self) -> list[dict]:
        out = []
        if self.rng.random() < 0.22:
            s = self.rng.choice(SYMBOLS)
            tpl, sent = self.rng.choice(NEWS_POOL)
            sev = round(self.rng.uniform(0.3, 0.95), 2)
            out.append({"ticker": s, "headline": tpl.format(t=s),
                        "body": f"Simulated corporate update for {s} on day {self.sim_day}.",
                        "sentiment": sent, "severity": sev, "sim_day": self.sim_day,
                        "ts": datetime.now(timezone.utc).isoformat()})
        return out

    def get_history(self, ticker: str, n: int = 100) -> list[dict]:
        return self.history.get(ticker, [])[-n:]

    def reset(self, seed: int = 42) -> None:
        self.__init__(seed)
