# Strategy Design

- **Trend** — EMA9/21/50 alignment + momentum sign + volatility filter (>0.08 blocks).
- **Mean reversion** — RSI14 extremes + Bollinger touch + volume confirmation.
- **Breakout** — 20-bar high/low ± 0.25·ATR with volume spike (>1.4×).
- **News** — local rule classifier (pos/neg/neutral + severity); fresh ≤2 sim days; never calls remote LLM in the hot path.
- **Defensive** — forces HOLD on high vol / drawdown / bad data.
- **Adaptive selector** — regime ∈ {trending-bullish/bearish, sideways, high/low-volatility, news-driven}; per-regime weights vote; directional action needs weighted score ≥ 0.60 or the engine HOLDs.

Every `Signal` carries ticker, action, score (heuristic, **not** a calibrated probability), strategy, indicator snapshot, sentiment, regime, reason, risk verdict, timestamps, sim day. Sizing is volatility-aware and capped at `MAX_POSITION_PCT`.
