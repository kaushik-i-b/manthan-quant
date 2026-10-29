"""Incremental rolling indicator engine. Only uses data available at decision time."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


def ema_update(prev: float | None, price: float, period: int) -> float:
    k = 2.0 / (period + 1)
    if prev is None:
        return price
    return price * k + prev * (k - 1) * -1 + prev * 0 if False else price * k + prev * (1 - k)


@dataclass
class SymbolState:
    closes: deque = field(default_factory=lambda: deque(maxlen=300))
    volumes: deque = field(default_factory=lambda: deque(maxlen=300))
    highs: deque = field(default_factory=lambda: deque(maxlen=300))
    lows: deque = field(default_factory=lambda: deque(maxlen=300))
    ema9: float | None = None
    ema21: float | None = None
    ema50: float | None = None
    prev_close: float | None = None
    gain_avg: float | None = None
    loss_avg: float | None = None
    macd_line: float | None = None
    macd_signal: float | None = None
    ema12: float | None = None
    ema26: float | None = None


class IndicatorEngine:
    def __init__(self) -> None:
        self.states: dict[str, SymbolState] = {}

    def _st(self, ticker: str) -> SymbolState:
        if ticker not in self.states:
            self.states[ticker] = SymbolState()
        return self.states[ticker]

    def on_candle(self, ticker: str, o: float, h: float, l: float, c: float, v: int) -> dict:
        st = self._st(ticker)
        st.closes.append(c)
        st.volumes.append(v)
        st.highs.append(h)
        st.lows.append(l)
        st.ema9 = ema_update(st.ema9, c, 9)
        st.ema21 = ema_update(st.ema21, c, 21)
        st.ema50 = ema_update(st.ema50, c, 50)
        st.ema12 = ema_update(st.ema12, c, 12)
        st.ema26 = ema_update(st.ema26, c, 26)
        macd = (st.ema12 or c) - (st.ema26 or c)
        st.macd_line = macd
        st.macd_signal = ema_update(st.macd_signal, macd, 9)
        # RSI-14 (Wilder)
        if st.prev_close is not None:
            gain = max(0.0, c - st.prev_close)
            loss = max(0.0, st.prev_close - c)
            if st.gain_avg is None:
                st.gain_avg, st.loss_avg = gain, loss
            else:
                st.gain_avg = (st.gain_avg * 13 + gain) / 14
                st.loss_avg = (st.loss_avg * 13 + loss) / 14
        st.prev_close = c
        return self.snapshot(ticker)

    def _sma(self, vals: deque, n: int) -> float | None:
        if len(vals) < n:
            return None
        return sum(list(vals)[-n:]) / n

    def snapshot(self, ticker: str) -> dict:
        st = self._st(ticker)
        closes = list(st.closes)
        vols = list(st.volumes)
        n = len(closes)
        sma20 = self._sma(st.closes, 20)
        sma50 = self._sma(st.closes, 50)
        # RSI
        rsi = None
        if st.gain_avg is not None and st.loss_avg is not None:
            if st.loss_avg == 0:
                rsi = 100.0 if st.gain_avg > 0 else 50.0
            else:
                rs = st.gain_avg / st.loss_avg
                rsi = 100 - 100 / (1 + rs)
        # Bollinger 20,2
        bb_upper = bb_lower = bb_mid = None
        if n >= 20:
            w = closes[-20:]
            mid = sum(w) / 20
            var = sum((x - mid) ** 2 for x in w) / 20
            sd = var ** 0.5
            bb_mid, bb_upper, bb_lower = mid, mid + 2 * sd, mid - 2 * sd
        # ATR-14
        atr = None
        if len(st.highs) >= 15:
            trs = []
            h, l, cl = list(st.highs), list(st.lows), closes
            for i in range(max(1, len(cl) - 14), len(cl)):
                trs.append(max(h[i] - l[i], abs(h[i] - cl[i - 1]), abs(l[i] - cl[i - 1])))
            atr = sum(trs) / len(trs) if trs else None
        # Volatility (stdev of last 20 returns), momentum, ROC
        vol = mom = roc = None
        if n >= 21:
            rets = [(closes[i] - closes[i - 1]) / max(closes[i - 1], 1e-9) for i in range(n - 20, n)]
            mean = sum(rets) / len(rets)
            vol = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5
            mom = closes[-1] - closes[-11] if n >= 11 else None
            roc = (closes[-1] - closes[-20]) / closes[-20] * 100 if closes[-20] else None
        # Volume anomaly
        vol_anom = None
        if len(vols) >= 20:
            avg = sum(vols[-20:]) / 20
            vol_anom = (vols[-1] / avg) if avg else None
        # Trend strength: ema alignment + distance
        trend = 0.0
        if st.ema9 and st.ema21 and st.ema50:
            if st.ema9 > st.ema21 > st.ema50:
                trend = 1.0
            elif st.ema9 < st.ema21 < st.ema50:
                trend = -1.0
            else:
                trend = 0.5 if (st.ema9 or 0) > (st.ema50 or 0) else -0.5
        last = closes[-1] if closes else None
        return {
            "price": last,
            "ema9": st.ema9, "ema21": st.ema21, "ema50": st.ema50,
            "sma20": sma20, "sma50": sma50,
            "rsi14": rsi,
            "macd": st.macd_line,
            "macd_signal": st.macd_signal,
            "macd_hist": (st.macd_line - st.macd_signal) if st.macd_line is not None and st.macd_signal is not None else None,
            "atr14": atr,
            "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
            "volatility": vol, "momentum": mom, "roc": roc,
            "volume_anomaly": vol_anom,
            "trend_strength": trend,
            "bars": n,
        }
