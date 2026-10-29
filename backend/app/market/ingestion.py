"""Kafka ingestion with mock fallback. Never blocks the event loop."""
from __future__ import annotations

import asyncio
import json
import time

from app.config import settings


class Ingestion:
    def __init__(self, bus, on_tick, on_news) -> None:
        self.bus = bus
        self.on_tick = on_tick
        self.on_news = on_news
        self.connected = False
        self.mode = "mock"
        self.lag = 0
        self.latency_ms = 0.0
        self.last_ts: float | None = None
        self._seen: set[str] = set()

    async def run(self) -> None:
        """Try real Kafka; fall back to mock stream. Reconnects with backoff."""
        try:
            from aiokafka import AIOKafkaConsumer  # type: ignore
        except Exception:
            self.mode = "mock-no-lib"
            return
        if settings.MOCK_MODE:
            self.mode = "mock"
            return
        backoff = 2
        while True:
            try:
                consumer = AIOKafkaConsumer(
                    settings.KAFKA_TOPIC_TICKS, settings.KAFKA_TOPIC_NEWS,
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    group_id=settings.KAFKA_GROUP_ID,
                    enable_auto_commit=False, auto_offset_reset="latest")
                await consumer.start()
                self.connected = True
                self.mode = "kafka"
                backoff = 2
                async for msg in consumer:
                    t0 = time.time()
                    try:
                        data = json.loads(msg.value.decode())
                        dedupe = f"{msg.topic}:{msg.partition}:{msg.offset}"
                        if dedupe in self._seen:
                            continue
                        self._seen.add(dedupe)
                        if msg.topic == settings.KAFKA_TOPIC_TICKS:
                            await self.on_tick(data)
                        else:
                            await self.on_news(data)
                        await consumer.commit()
                        self.latency_ms = (time.time() - t0) * 1000
                        self.last_ts = time.time()
                        self.lag = max(0, (msg.timestamp or 0) and 0)
                    except Exception:
                        continue
            except Exception:
                self.connected = False
                self.mode = "mock"
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
