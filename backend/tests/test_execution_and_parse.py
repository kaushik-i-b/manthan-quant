"""Rate limit, retries, schema rejection, and tape ordering."""

import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.execution.client import ApiError, TradingApiClient
from app.execution.rate_limit import RateLimiter
from app.execution.templates import render
from app.market.book import TickerTape
from app.market.parse import SchemaRejected, consume_decoded, parse_news, parse_tick
from app.models.types import Candle
from app.sentiment.lexicon import score_text


def _candle(day: int, event_id: str | None = None) -> Candle:
    return Candle(
        event_id=event_id or f"T-{day}",
        ticker="T",
        sim_day=day,
        ts_unix=1_700_000_000 + day,
        open=10,
        high=11,
        low=9,
        close=10,
        volume=100,
        source="synthetic",
    )


def test_rate_limiter_blocks_when_budget_is_spent() -> None:
    clock = {"now": 0.0}
    limiter = RateLimiter(limit=3, window_sec=60, clock=lambda: clock["now"])
    assert limiter.try_acquire()
    assert limiter.try_acquire()
    assert limiter.try_acquire()
    assert limiter.try_acquire() is False
    assert limiter.remaining() == 0
    clock["now"] = 61
    assert limiter.try_acquire() is True


@pytest.mark.asyncio
async def test_get_retries_and_order_does_not() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path.endswith("/stocks") and calls["n"] < 3:
            return httpx.Response(503, json={"error": "busy"})
        if request.url.path.endswith("/orders"):
            raise httpx.TimeoutException("timed out")
        return httpx.Response(200, json={"ok": True, "rows": ["RELIANCE"]})

    settings = Settings(bot_access_token="secret-token", api_timeout_sec=1)
    client = TradingApiClient(settings, RateLimiter(100), transport=httpx.MockTransport(handler))
    payload = await client.get_stocks()
    assert payload["rows"] == ["RELIANCE"]
    stock_calls = calls["n"]
    assert stock_calls == 3
    with pytest.raises(ApiError) as caught:
        await client.post_order({"ticker": "RELIANCE"})
    assert caught.value.kind == "timeout"
    assert calls["n"] == stock_calls + 1
    await client.aclose()


def test_template_render_is_exact() -> None:
    rendered = render(
        {"symbol": "{ticker}", "side": "{action}", "qty": "{quantity}"},
        {"ticker": "INFY", "action": "BUY", "quantity": "4"},
    )
    assert rendered == {"symbol": "INFY", "side": "BUY", "qty": "4"}


def test_parser_rejects_unknown_schema_and_accepts_internal() -> None:
    candle = _candle(1)
    parsed = parse_tick(json.loads(candle.model_dump_json()))
    assert parsed.ticker == "T"
    with pytest.raises(SchemaRejected):
        parse_tick({"ticker": "T", "close": 1})
    news = {
        "schema_name": "manthan-quant.internal.news.v1",
        "event_id": "n1",
        "ticker": "HDFCBANK",
        "sim_day": 82,
        "ts_unix": 1,
        "headline": "HDFCBANK discloses major loss amid fraud investigation",
        "body": "downgrade",
        "source": "synthetic",
    }
    item = parse_news(news)
    sentiment, severity, label = score_text(item.headline + " " + item.body)
    assert label == "negative"
    assert sentiment < -0.4
    assert severity > 0.5


def test_tape_drops_duplicates_and_reorders() -> None:
    tape = TickerTape()
    assert tape.add(_candle(1))
    assert tape.add(_candle(1, event_id="other")) is False
    assert tape.dropped_reorder == 1
    assert tape.add(_candle(2))
    assert tape.add(_candle(2)) is False
    assert tape.dropped_duplicate == 1
    assert tape.add(_candle(4))
    assert tape.gaps == 1
    assert [c.sim_day for c in tape.candles] == [1, 2, 4]


@pytest.mark.asyncio
async def test_consume_loop_commits_poison_and_valid_messages() -> None:
    committed = []

    async def handler(message: dict) -> None:
        parse_tick(message)

    async def commit(message: dict) -> None:
        committed.append(message["event_id"])

    stats = await consume_decoded(
        [
            json.loads(_candle(1, "ok").model_dump_json()),
            {"event_id": "bad", "ticker": "T"},
        ],
        handler,
        commit,
    )
    assert stats == {"handled": 1, "rejected": 1}
    assert committed == ["ok", "bad"]


def test_order_template_file_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "order.json"
    path.write_text(json.dumps({"symbol": "{ticker}", "qty": "{quantity}"}))
    from app.execution.templates import load_template

    assert load_template(str(path))["symbol"] == "{ticker}"
