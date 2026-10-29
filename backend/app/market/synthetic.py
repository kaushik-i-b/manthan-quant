"""Deterministic synthetic tape.

Prices are generated, not sampled from a venue. Every candle is tagged
source='synthetic'. The shapes are built so the desk can demonstrate trend,
breakout, mean-reversion, and news paths without pretending they are history.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.models.types import Candle, NewsItem

# Fixed origin so chart time is stable. It is a simulated clock, not a session date.
SYNTHETIC_EPOCH = 1_704_067_200

UNIVERSE: list[tuple[str, str]] = [
    ("BHARTIARTL", "Bharti Airtel"),
    ("HDFCBANK", "HDFC Bank"),
    ("ICICIBANK", "ICICI Bank"),
    ("INFY", "Infosys"),
    ("ITC", "ITC"),
    ("RELIANCE", "Reliance Industries"),
    ("SBIN", "State Bank of India"),
    ("TCS", "Tata Consultancy Services"),
]


@dataclass
class SyntheticDataset:
    candles: dict[str, list[Candle]]
    news: list[NewsItem]
    names: dict[str, str]
    seed: int
    days: int
    disclaimer: str = (
        "Synthetic demonstration tape. Not exchange history and not a competition result."
    )


def _ohlc(ticker: str, closes: list[float], volumes: list[float]) -> list[Candle]:
    candles: list[Candle] = []
    prev = closes[0]
    for day, close in enumerate(closes):
        open_ = prev if day else close
        high = max(open_, close) * 1.002
        low = min(open_, close) * 0.998
        candles.append(
            Candle(
                event_id=f"{ticker}-{day}",
                ticker=ticker,
                sim_day=day,
                ts_unix=SYNTHETIC_EPOCH + day * 86400,
                open=round(open_, 4),
                high=round(high, 4),
                low=round(low, 4),
                close=round(close, 4),
                volume=float(volumes[day]),
                source="synthetic",
            )
        )
        prev = close
    return candles


def _volumes(n: int, base: float, spikes: dict[int, float]) -> list[float]:
    out = []
    for day in range(n):
        factor = spikes.get(day, 1.0)
        out.append(base * factor)
    return out


def _flat_then_drift(start: float, n: int, turn: int, daily: float) -> list[float]:
    """Quiet two-sided wiggle, then a deterministic drift.

    The wiggle keeps RSI and ATR mathematically alive. A perfectly flat
    series would pin RSI at the 0/0 boundary and then jump to 100 on the
    first up bar, which is an artifact rather than a market regime.
    """
    closes = []
    for day in range(n):
        if day < turn:
            wiggle = 1.0015 if day % 2 == 0 else 0.9985
            closes.append(start * wiggle)
        else:
            closes.append(start * ((1.0 + daily) ** (day - turn + 1)))
    return closes


def _dip_cycle(start: float, n: int) -> list[float]:
    closes = []
    for day in range(n):
        cycle = day % 30
        if 20 <= cycle <= 22:
            closes.append(start * 0.93)
        elif cycle > 22:
            # climb back over the rest of the cycle
            progress = (cycle - 22) / 8.0
            closes.append(start * (0.93 + 0.07 * min(progress, 1.0)))
        else:
            closes.append(start)
    return closes


def _gap_down(start: float, n: int, gap_day: int) -> list[float]:
    closes = []
    for day in range(n):
        if day < gap_day:
            closes.append(start)
        elif day == gap_day:
            closes.append(start * 0.92)
        else:
            closes.append(start * 0.92 * ((0.997) ** (day - gap_day)))
    return closes


def _noisy(start: float, n: int, seed: int, vol: float, drift: float) -> list[float]:
    rng = np.random.default_rng(seed)
    price = float(start)
    closes = []
    for _ in range(n):
        shock = float(rng.normal(drift, vol))
        price = max(20.0, price * (1.0 + shock))
        closes.append(price)
    return closes


def build_dataset(seed: int = 42, days: int = 160) -> SyntheticDataset:
    if days < 80:
        raise ValueError("synthetic tape needs at least 80 days")
    series = {
        "RELIANCE": _flat_then_drift(2450.0, days, 75, 0.006),
        "BHARTIARTL": _flat_then_drift(1450.0, days, 88, 0.005),
        "ICICIBANK": _flat_then_drift(1100.0, days, 80, -0.005),
        "INFY": _flat_then_drift(1520.0, days, 90, 0.012),
        "HDFCBANK": _gap_down(1650.0, days, 82),
        "TCS": _dip_cycle(3800.0, days),
        "ITC": _noisy(460.0, days, seed + 11, 0.004, 0.0),
        "SBIN": _noisy(780.0, days, seed + 19, 0.005, 0.0004),
    }
    volume_bases = {
        "RELIANCE": 2_400_000,
        "BHARTIARTL": 1_800_000,
        "ICICIBANK": 2_100_000,
        "INFY": 1_600_000,
        "HDFCBANK": 1_900_000,
        "TCS": 1_200_000,
        "ITC": 900_000,
        "SBIN": 3_000_000,
    }
    spikes = {
        "INFY": {90: 4.0, 91: 2.4, 92: 1.8},
        "HDFCBANK": {82: 3.2, 83: 2.0},
        "TCS": {20: 2.2, 50: 2.2, 80: 2.5, 110: 2.2, 140: 2.2},
        "RELIANCE": {75: 1.8},
    }
    candles = {
        ticker: _ohlc(ticker, closes, _volumes(days, volume_bases[ticker], spikes.get(ticker, {})))
        for ticker, closes in series.items()
    }
    headlines = [
        (
            76,
            "RELIANCE",
            "RELIANCE reports record profit, expansion plan and dividend increase",
            "Management guided for growth and a higher dividend after record profit.",
        ),
        (
            82,
            "HDFCBANK",
            "HDFCBANK discloses major loss amid fraud investigation and downgrade",
            "A fraud investigation, a major loss, and a downgrade hit the bank.",
        ),
        (
            90,
            "INFY",
            "INFY wins record deal and receives an upgrade on growth",
            "A record contract win and an analyst upgrade supported the growth outlook.",
        ),
        (
            121,
            "SBIN",
            "SBIN warns of sharp decline in margins",
            "The bank warned of a sharp decline in margins.",
        ),
    ]
    news = [
        NewsItem(
            event_id=f"news-{ticker}-{day}",
            ticker=ticker,
            sim_day=day,
            ts_unix=SYNTHETIC_EPOCH + day * 86400,
            headline=headline,
            body=body,
            source="synthetic",
        )
        for day, ticker, headline, body in headlines
        if day < days
    ]
    return SyntheticDataset(
        candles=candles,
        news=news,
        names={ticker: name for ticker, name in UNIVERSE},
        seed=seed,
        days=days,
    )
