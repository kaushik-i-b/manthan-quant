# Jury Demo — 5-minute script (deterministic seed 42)

1. **Market alive (30 s)** — Overview: sim day advancing, equity curve ticking, status bar green TRADING ACTIVE + DRY RUN.
2. **Tick → indicator (45 s)** — Market Terminal: pick RELIANCE, show RSI/EMA values moving; note incremental engine (no recompute).
3. **Signal (60 s)** — AI Strategy Center: read the decision card aloud — ticker, action, score, regime, reason.
4. **Risk veto (45 s)** — Risk Center: press *Pause trading*, point to next signal rejected with reason; resume.
5. **Order → P&L (45 s)** — Execution Monitor: show CONFIRMED mock-fill with close-price fill; Portfolio cash/equity updates.
6. **Resilience (30 s)** — kill network / keep Kafka mock: engine keeps deciding, dashboard shows stale flag then recovers via auto-reconnect.
7. **Backtest (45 s)** — Backtest Lab: run all strategies, read table + buy&hold baseline; state clearly: synthetic seed-42 data, labeled.

One command: `bash scripts/demo.sh`, then open http://127.0.0.1:43123.
