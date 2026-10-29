# Five-minute jury script

Say at the start: the prices are a synthetic tape, the banner says so, and no order is sent to the venue. `DRY_RUN` is on.

1. **Tape (20s).** Open Overview. The lamp is PREFLIGHT, then LIVE. Kafka is disabled on purpose. The API pill says `not_contacted`. Sim day starts counting from 71.
2. **Indicators (30s).** Open Market. Pick RELIANCE. Candles, volume, and EMA 9/21/50 are already warm. Toggle RSI. The watchlist is the engine universe, not a hardcoded page.
3. **Signal (40s).** Around day 76 the news headline on RELIANCE and the trend score produce a BUY. Open Strategy. Read the decision card: action, heuristic score, regime, RSI, news label, and the sentence the engine stored. Do not add a reason that is not on the card.
4. **Risk and fill (40s).** Execution shows the fill at the candle close on the mock book, with the ₹15 synthetic brokerage labeled unofficial. Portfolio moves cash, quantity, and unrealized P&L.
5. **Round trip (30s).** Stay on Portfolio. A take-profit or later exit updates realized P&L. Win rate stays "—" until a round trip closes, then it is the closed-trade rate.
6. **Unsafe order (40s).** Day 78 inserts a billion-share BUY. Risk rejects it. Open Risk and read the rejection: cash and position cap. No fill was created.
7. **Outage (40s).** Click **Simulate feed outage**. The feed pill goes interrupted and the lamp leaves LIVE. After about six seconds it recovers and the milestone "Recovered" lights. Entries were blocked during the gap.
8. **Lab (40s).** Backtesting lab → Run comparison. Point at the ranking, the equity curves, and the test-window row. Say the threshold was chosen on the train split only, and the numbers are synthetic.

If the venue network is up, stop before claiming a live fill. `make probe` only checks that `/stage` answers.
