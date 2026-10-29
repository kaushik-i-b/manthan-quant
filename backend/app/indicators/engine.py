"""Incremental indicators.

Every update uses only the current bar and retained state. No future bars
are readable from this module. Bollinger standard deviation is the population
statistic (divisor n), matching the common charting convention.
"""

from __future__ import annotations

import math
from collections import deque

from app.models.types import Candle, IndicatorSnapshot


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


class EMA:
    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError("period must be positive")
        self.period = period
        self.k = 2.0 / (period + 1.0)
        self.value: float | None = None
        self._seed: list[float] = []

    def update(self, price: float) -> float | None:
        if self.value is None:
            self._seed.append(price)
            if len(self._seed) < self.period:
                return None
            self.value = sum(self._seed) / self.period
            return self.value
        self.value = price * self.k + self.value * (1.0 - self.k)
        return self.value


class SMA:
    def __init__(self, period: int) -> None:
        self.period = period
        self.window: deque[float] = deque()
        self.total = 0.0

    def update(self, price: float) -> float | None:
        self.window.append(price)
        self.total += price
        if len(self.window) > self.period:
            self.total -= self.window.popleft()
        if len(self.window) < self.period:
            return None
        return self.total / self.period


class RSI:
    """Wilder RSI. Flat series resolve to 50. No losses resolve to 100."""

    def __init__(self, period: int = 14) -> None:
        self.period = period
        self.prev: float | None = None
        self.avg_gain: float | None = None
        self.avg_loss: float | None = None
        self._gains: list[float] = []
        self._losses: list[float] = []

    def update(self, price: float) -> float | None:
        if self.prev is None:
            self.prev = price
            return None
        change = price - self.prev
        self.prev = price
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        if self.avg_gain is None:
            self._gains.append(gain)
            self._losses.append(loss)
            if len(self._gains) < self.period:
                return None
            self.avg_gain = sum(self._gains) / self.period
            self.avg_loss = sum(self._losses) / self.period
        else:
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period
        assert self.avg_gain is not None and self.avg_loss is not None
        if self.avg_gain == 0 and self.avg_loss == 0:
            return 50.0
        if self.avg_loss == 0:
            return 100.0
        rs = self.avg_gain / self.avg_loss
        return 100.0 - (100.0 / (1.0 + rs))


class MACD:
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
        self.fast = EMA(fast)
        self.slow = EMA(slow)
        self.signal = EMA(signal)

    def update(self, price: float) -> tuple[float | None, float | None, float | None]:
        fast = self.fast.update(price)
        slow = self.slow.update(price)
        if fast is None or slow is None:
            return None, None, None
        macd = fast - slow
        sig = self.signal.update(macd)
        hist = None if sig is None else macd - sig
        return macd, sig, hist


class ATR:
    def __init__(self, period: int = 14) -> None:
        self.period = period
        self.prev_close: float | None = None
        self._trs: list[float] = []
        self.value: float | None = None

    def update(self, high: float, low: float, close: float) -> float | None:
        if self.prev_close is None:
            self.prev_close = close
            return None
        tr = max(high - low, abs(high - self.prev_close), abs(low - self.prev_close))
        self.prev_close = close
        if self.value is None:
            self._trs.append(tr)
            if len(self._trs) < self.period:
                return None
            self.value = sum(self._trs) / self.period
            return self.value
        self.value = (self.value * (self.period - 1) + tr) / self.period
        return self.value


class Bollinger:
    def __init__(self, period: int = 20, mult: float = 2.0) -> None:
        self.period = period
        self.mult = mult
        self.window: deque[float] = deque()
        self.total = 0.0
        self.sumsq = 0.0

    def update(self, price: float) -> tuple[float | None, float | None, float | None, float | None]:
        self.window.append(price)
        self.total += price
        self.sumsq += price * price
        if len(self.window) > self.period:
            old = self.window.popleft()
            self.total -= old
            self.sumsq -= old * old
        if len(self.window) < self.period:
            return None, None, None, None
        mean = self.total / self.period
        var = max(self.sumsq / self.period - mean * mean, 0.0)
        std = math.sqrt(var)
        upper = mean + self.mult * std
        lower = mean - self.mult * std
        width = (upper - lower) / mean if mean else None
        return mean, upper, lower, width


class RollingVol:
    def __init__(self, period: int = 20) -> None:
        self.period = period
        self.prev: float | None = None
        self.window: deque[float] = deque()

    def update(self, price: float) -> float | None:
        if self.prev is None or self.prev == 0:
            self.prev = price
            return None
        ret = price / self.prev - 1.0
        self.prev = price
        self.window.append(ret)
        if len(self.window) > self.period:
            self.window.popleft()
        if len(self.window) < self.period:
            return None
        mean = sum(self.window) / len(self.window)
        var = sum((item - mean) ** 2 for item in self.window) / len(self.window)
        return math.sqrt(max(var, 0.0))


class LookbackReturn:
    def __init__(self, period: int) -> None:
        self.period = period
        self.window: deque[float] = deque()

    def update(self, price: float) -> float | None:
        self.window.append(price)
        if len(self.window) > self.period + 1:
            self.window.popleft()
        if len(self.window) < self.period + 1:
            return None
        base = self.window[0]
        if base == 0:
            return None
        return price / base - 1.0


class VolumeRatio:
    """Current volume divided by the average of the previous `period` volumes."""

    def __init__(self, period: int = 20) -> None:
        self.period = period
        self.window: deque[float] = deque()

    def update(self, volume: float) -> float | None:
        ratio = None
        if len(self.window) >= self.period:
            avg = sum(self.window) / len(self.window)
            ratio = volume / avg if avg else None
        self.window.append(volume)
        if len(self.window) > self.period:
            self.window.popleft()
        return ratio


class PriorRange:
    def __init__(self, period: int = 20) -> None:
        self.period = period
        self.highs: deque[float] = deque()
        self.lows: deque[float] = deque()

    def update(self, high: float, low: float) -> tuple[float | None, float | None]:
        prior_high = max(self.highs) if len(self.highs) >= self.period else None
        prior_low = min(self.lows) if len(self.lows) >= self.period else None
        self.highs.append(high)
        self.lows.append(low)
        if len(self.highs) > self.period:
            self.highs.popleft()
            self.lows.popleft()
        return prior_high, prior_low


class IndicatorEngine:
    def __init__(self) -> None:
        self.ema9 = EMA(9)
        self.ema21 = EMA(21)
        self.ema50 = EMA(50)
        self.sma20 = SMA(20)
        self.sma50 = SMA(50)
        self.rsi = RSI(14)
        self.macd = MACD()
        self.atr = ATR(14)
        self.bb = Bollinger(20, 2.0)
        self.vol = RollingVol(20)
        self.momentum = LookbackReturn(10)
        self.volume_ratio = VolumeRatio(20)
        self.prior = PriorRange(20)
        self.peak: float | None = None
        self.bars = 0
        self.last = IndicatorSnapshot()

    def update(self, candle: Candle) -> IndicatorSnapshot:
        close = candle.close
        if not all(_finite(v) for v in (candle.open, candle.high, candle.low, close, candle.volume)):
            snap = self.last.model_copy(update={"ready": False})
            self.last = snap
            return snap
        if min(candle.open, candle.high, candle.low, close) <= 0 or candle.high < candle.low:
            snap = self.last.model_copy(update={"ready": False})
            self.last = snap
            return snap

        ema9 = self.ema9.update(close)
        ema21 = self.ema21.update(close)
        ema50 = self.ema50.update(close)
        sma20 = self.sma20.update(close)
        sma50 = self.sma50.update(close)
        rsi = self.rsi.update(close)
        macd, sig, hist = self.macd.update(close)
        atr = self.atr.update(candle.high, candle.low, close)
        mid, upper, lower, width = self.bb.update(close)
        volatility = self.vol.update(close)
        momentum = self.momentum.update(close)
        roc = None if momentum is None else momentum * 100.0
        volume_ratio = self.volume_ratio.update(candle.volume)
        prior_high, prior_low = self.prior.update(candle.high, candle.low)
        self.peak = close if self.peak is None else max(self.peak, close)
        drawdown = (self.peak - close) / self.peak if self.peak else 0.0
        trend = None
        if ema9 is not None and ema21 is not None and atr and atr > 0:
            trend = abs(ema9 - ema21) / atr
        self.bars += 1
        ready = ema50 is not None and rsi is not None and atr is not None and sma20 is not None
        snap = IndicatorSnapshot(
            ready=ready,
            close=close,
            ema9=ema9,
            ema21=ema21,
            ema50=ema50,
            sma20=sma20,
            sma50=sma50,
            rsi14=rsi,
            macd=macd,
            macd_signal=sig,
            macd_hist=hist,
            atr14=atr,
            bb_mid=mid,
            bb_upper=upper,
            bb_lower=lower,
            bb_width=width,
            volatility20=volatility,
            momentum10=momentum,
            roc10=roc,
            volume_ratio20=volume_ratio,
            trend_strength=trend,
            prior_high20=prior_high,
            prior_low20=prior_low,
            price_drawdown=drawdown,
        )
        self.last = snap
        return snap
