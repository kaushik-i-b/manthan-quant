# Architecture

```
Kafka (market.ticks/news) ──┐
                            ▼
                    Ingestion (aiokafka, manual commits, reconnect backoff)
                            │ normalized Tick/NewsEvent
                    ┌────────┴────────┐
                    ▼                 ▼
            IndicatorEngine    Sentiment (local rules)
            (incremental       │
             EMA/RSI/MACD/      │
             ATR/BB/…)          ▼
                    Strategy votes (trend/meanrev/breakout/news) → regime → combine
                            │ Signal (ticker/action/score/reason/day)
                            ▼
                    RiskEngine (independent veto + volatility sizing)
                            │ OrderIntent
                            ▼
                    Executor (single-writer queue → ApiClient → reconcile → audit)
                            │ fill at close price (sim rule)
                            ▼
                    Portfolio (cash/holdings/shorts/fees/equity history)
                            │
                     WebSocket bus ──► Next.js terminal (7 screens)
```

- Trading path never touches remote LLMs; sentiment is a local classifier.
- Heartbeat/lifecycle runs on its own asyncio task, independent of analytics.
- Dashboard disconnect never blocks the engine; engine never blocks on rendering.
- SQLite persistence hook lives in `persistence/` (audit log); equity history is in-memory + API for the demo slice.
