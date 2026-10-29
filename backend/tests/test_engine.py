"""Indicator correctness, strategy, risk, portfolio, sentiment tests."""
from app.indicators.engine import IndicatorEngine
from app.models.schemas import Action, Signal
from app.portfolio.manager import Portfolio
from app.risk.engine import RiskEngine
from app.sentiment.analyzer import classify
from app.strategies import engine as strat
from app.strategies.engine import Ctx


def feed(engine, ticker, closes, vol=1000):
    out = None
    for c in closes:
        out = engine.on_candle(ticker, c, c * 1.01, c * 0.99, c, vol)
    return out


def test_ema_trend_up():
    e = IndicatorEngine()
    s = feed(e, "T", [100 + i for i in range(60)])
    assert s["ema9"] > s["ema21"] > s["ema50"]
    assert s["trend_strength"] == 1.0


def test_rsi_bounds():
    e = IndicatorEngine()
    s = feed(e, "T", [100.0] * 30)
    assert s["rsi14"] == 50.0
    s2 = feed(e, "U", [100 + i * 2 for i in range(30)])
    assert s2["rsi14"] > 70


def test_bollinger_flat():
    e = IndicatorEngine()
    s = feed(e, "T", [100.0] * 25)
    assert abs(s["bb_upper"] - 100.0) < 1e-6
    assert abs(s["bb_lower"] - 100.0) < 1e-6


def test_trend_strategy_holds_without_history():
    e = IndicatorEngine()
    s = feed(e, "T", [100.0] * 5)
    sig = strat.trend_strategy(Ctx("T", s))
    assert sig.action == Action.HOLD


def test_meanrev_oversold_buy():
    e = IndicatorEngine()
    closes = [100 - i * 1.5 for i in range(30)]  # steady fall -> oversold
    s = feed(e, "T", closes)
    sig = strat.mean_reversion_strategy(Ctx("T", s))
    assert sig.strategy == "meanrev"
    assert sig.action in (Action.BUY, Action.HOLD)


def test_breakout_buy():
    e = IndicatorEngine()
    for c in [100.0] * 24:
        e.on_candle("T", c, c * 1.005, c * 0.995, c, 500)
    s = e.on_candle("T", 115.0, 116.0, 114.0, 115.0, 5000)
    sig = strat.breakout_strategy(Ctx("T", s), recent_high=101.0, recent_low=99.0)
    assert sig.action == Action.BUY


def test_news_strategy():
    s = strat.news_strategy(Ctx("T", {}, sentiment="positive", severity=0.8, news_fresh=True))
    assert s.action == Action.BUY
    s2 = strat.news_strategy(Ctx("T", {}, sentiment="neutral", severity=0.0, news_fresh=False))
    assert s2.action == Action.HOLD


def test_regime_classifier():
    assert strat.classify_regime({"trend_strength": 1.0, "volatility": 0.01}, False, "neutral") == "trending-bullish"
    assert strat.classify_regime({"trend_strength": 0, "volatility": 0.2}, False, "neutral") == "high-volatility"
    assert strat.classify_regime({"trend_strength": 0, "volatility": 0.01}, True, "positive") == "news-driven"


def test_combine_holds_without_consensus():
    a = Signal(ticker="T", action=Action.HOLD, score=0.5, strategy="trend", reason="x")
    out = strat.combine([a], "sideways")
    assert out.action == Action.HOLD
    assert "contributions" in out.indicators


def test_sentiment_classifier():
    s, sev = classify("Company reports record profit and beats estimates")
    assert s == "positive" and sev > 0
    s2, _ = classify("Regulator probes company over fraud allegations")
    assert s2 == "negative"


def test_risk_blocks_when_paused():
    r = RiskEngine()
    r.set_paused(True, "manual")
    sig = Signal(ticker="T", action=Action.BUY, score=0.8, strategy="trend", reason="x", sim_day=1)
    d = r.evaluate(sig, 1_000_000, 1_000_000, {}, 100.0, 0.0, 0, True, False, True)
    assert not d.passed


def test_risk_respects_cash_reserve():
    r = RiskEngine()
    sig = Signal(ticker="T", action=Action.BUY, score=0.9, strategy="trend", reason="x", sim_day=1)
    d = r.evaluate(sig, 10_000, 1_000_000, {}, 100.0, 0.0, 0, True, False, True)
    assert not d.passed and "reserve" in d.reason


def test_risk_duplicate_orders_per_day_cap():
    r = RiskEngine()
    r.s.MAX_ORDERS_PER_DAY = 1
    sig = Signal(ticker="T", action=Action.BUY, score=0.9, strategy="trend",
                 indicators={"volatility": 0.02}, reason="x", sim_day=5)
    d1 = r.evaluate(sig, 1_000_000, 1_000_000, {}, 100.0, 0.0, 0, True, False, True)
    assert d1.passed
    r.record_fill()
    d2 = r.evaluate(sig, 1_000_000, 1_000_000, {}, 100.0, 0.0, 0, True, False, True)
    assert not d2.passed


def test_portfolio_buy_sell_roundtrip():
    pf = Portfolio(100_000)
    pf.apply_fill("T", Action.BUY, 100, 100.0)
    assert pf.pos("T").qty == 100
    assert pf.cash < 100_000
    px = {"T": 110.0}
    snap = pf.snapshot(px, 1)
    assert snap.unrealized_pnl > 0
    pf.apply_fill("T", Action.SELL, 100, 110.0)
    assert pf.pos("T").qty == 0
    assert pf.realized > 0


def test_portfolio_short_cover():
    pf = Portfolio(100_000)
    pf.apply_fill("T", Action.SHORT, 50, 100.0)
    assert pf.pos("T").short_qty == 50
    pf.apply_fill("T", Action.COVER, 50, 90.0)
    assert pf.pos("T").short_qty == 0
    assert pf.realized > 0


def test_backtest_no_lookahead():
    from app.backtesting.engine import run_backtest
    candles = {"A": [{"open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i, "volume": 1000} for i in range(80)]}
    out = run_backtest(candles, "trend", starting=100_000)
    assert out["final_equity"] > 0
    assert "max_drawdown_pct" in out
