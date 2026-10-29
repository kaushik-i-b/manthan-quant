# Strategy design

Every score is a heuristic in [-1, 1]. It is not a probability. The desk prints `score_type: heuristic`.

| Strategy | Idea |
| --- | --- |
| Trend | EMA9 vs EMA21, EMA21 vs EMA50, 10-bar momentum. High volatility or an extreme RSI dampens the score. |
| Mean reversion | RSI 30/70, close outside Bollinger bands (population std, 20, 2σ), distance from SMA20, volume confirmation. |
| Breakout | Close through the prior 20-bar high or low, with a larger score when volume is at least 1.8× the prior average. |
| News | Local lexicon on the headline and body. Severity decays with age. No remote model call. |
| Defensive | Forces flat exposure when data is stale, drawdown is near the cap, or volatility is extreme. |

The selector classifies a regime per ticker (trending bullish/bearish, sideways, high/low volatility, news-driven, unreliable) and applies fixed weights. A combined score inside ±`ENTRY_THRESHOLD` (default 0.45) is a HOLD, which is a normal outcome.

Entries are volatility-sized: risk budget is `RISK_PER_TRADE_PCT` of equity per ATR, then capped at `MAX_POSITION_PCT`. Exits use the full position. Stop-loss (4%) and take-profit (8%) are evaluated at the candle close, because the simulator does not fill inside the bar. Shorts are covered after `SHORT_MAX_HOLD_DAYS` under the local rule.

Baselines used only in the lab: buy-and-hold (8% each, no stops), sign-of-momentum, RSI-only mean reversion, and cash.

The synthetic tape is deterministic for seed 42. RELIANCE and BHARTIARTL trend up after a quiet period, ICICIBANK trends down, INFY breaks out with a volume spike, HDFCBANK gaps down on a negative headline, and TCS repeats a dip cycle. ITC and SBIN are seeded noise. None of these paths are exchange history.
