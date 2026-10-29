"""Indicator values checked against hand calculations and an independent NumPy oracle."""

import math

import numpy as np
import pytest

from app.indicators.engine import ATR, Bollinger, EMA, IndicatorEngine, MACD, RSI, SMA
from app.models.types import Candle


def _candle(close: float, high: float | None = None, low: float | None = None, volume: float = 1000, day: int = 0) -> Candle:
    high = close if high is None else high
    low = close if low is None else low
    return Candle(
        event_id=f"t-{day}-{close}",
        ticker="TEST",
        sim_day=day,
        ts_unix=1_700_000_000 + day * 86400,
        open=close,
        high=high,
        low=low,
        close=close,
        volume=volume,
        source="synthetic",
    )


def test_ema_matches_hand_seed() -> None:
    ema = EMA(3)
    assert ema.update(1) is None
    assert ema.update(2) is None
    assert ema.update(3) == pytest.approx(2.0)
    assert ema.update(4) == pytest.approx(3.0)
    assert ema.update(5) == pytest.approx(4.0)


def test_sma_running_sum() -> None:
    sma = SMA(5)
    values = list(range(1, 11))
    last = None
    for value in values:
        last = sma.update(float(value))
    assert last == pytest.approx(8.0)


def test_rsi_hand_period_3() -> None:
    rsi = RSI(3)
    prices = [10, 11, 12, 11, 10, 13]
    outputs = [rsi.update(price) for price in prices]
    assert outputs[0] is None
    assert outputs[3] == pytest.approx(100 - 100 / 3)
    assert outputs[4] == pytest.approx(100 - 100 / 1.8)
    assert outputs[5] == pytest.approx(100 - 100 / 4.5)


def test_rsi_flat_is_50_and_extreme_jump_does_not_throw() -> None:
    rsi = RSI(3)
    for price in (5, 5, 5, 5):
        value = rsi.update(price)
    assert value == pytest.approx(50.0)
    jumped = RSI(3)
    for price in (10, 10, 10, 10, 10_000):
        value = jumped.update(price)
    assert value == pytest.approx(100.0)


def test_macd_is_fast_minus_slow_once_both_exist() -> None:
    macd = MACD(fast=3, slow=5, signal=3)
    prices = [float(i) for i in range(1, 12)]
    fast = EMA(3)
    slow = EMA(5)
    last = (None, None, None)
    for price in prices:
        last = macd.update(price)
        fast_value = fast.update(price)
        slow_value = slow.update(price)
        if fast_value is not None and slow_value is not None:
            assert last[0] == pytest.approx(fast_value - slow_value)


def test_bollinger_matches_numpy_population_std() -> None:
    bb = Bollinger(20, 2)
    prices = np.arange(1, 21, dtype=float)
    result = None
    for price in prices:
        result = bb.update(float(price))
    mean = float(prices.mean())
    std = float(prices.std(ddof=0))
    assert result[0] == pytest.approx(mean)
    assert result[1] == pytest.approx(mean + 2 * std)
    assert result[2] == pytest.approx(mean - 2 * std)


def test_atr_first_value_is_mean_true_range() -> None:
    atr = ATR(3)
    bars = [(10, 9, 10), (12, 10, 11), (11, 8, 9), (13, 9, 12)]
    values = [atr.update(high, low, close) for high, low, close in bars]
    # True ranges from the second bar onward.
    trs = [
        max(12 - 10, abs(12 - 10), abs(10 - 10)),
        max(11 - 8, abs(11 - 11), abs(8 - 11)),
        max(13 - 9, abs(13 - 9), abs(9 - 9)),
    ]
    assert values[3] == pytest.approx(sum(trs) / 3)


def test_engine_does_not_change_past_snapshot_when_future_arrives() -> None:
    engine = IndicatorEngine()
    past = None
    for day in range(60):
        past = engine.update(_candle(100 + day * 0.1, high=101 + day * 0.1, low=99 + day * 0.1, day=day))
    assert past is not None and past.ema50 is not None
    frozen = past.model_copy()
    engine.update(_candle(50, high=80, low=40, day=60))
    assert past.ema50 == frozen.ema50
    assert past.rsi14 == frozen.rsi14


def test_invalid_candle_does_not_crash() -> None:
    engine = IndicatorEngine()
    snap = engine.update(_candle(math.nan, day=0))
    assert snap.ready is False
    snap = engine.update(_candle(-1, day=1))
    assert snap.ready is False
