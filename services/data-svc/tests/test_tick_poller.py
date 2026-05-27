"""Tests for data-svc TickPoller.

All tests use unittest.mock.AsyncMock for KalshiClient and NATSPublisher —
no real network, no real broker.

Covers:
- _market_to_event converts a valid Kalshi market dict
- _market_to_event skips markets with an empty book on any side
- _market_to_event falls back through the three Kalshi volume field names
- _poll_once publishes one event per valid market, counts skips correctly
- tick_poll_loop propagates CancelledError so shutdown actually terminates
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data_svc.tick_poller import (
    _market_to_event,
    _poll_once,
    tick_poll_loop,
)

# File-scoped marker — every test in this file is async (poller and its
# helpers are all coroutines). Same pattern as test_nats_publisher.py.
pytestmark = pytest.mark.asyncio


def _valid_market_dict(**overrides: Any) -> dict[str, Any]:
    """Canonical valid Kalshi /markets dict for tests.

    Field names and values mirror the live Kalshi API (verified 2026-05-26).
    Prices are dollar strings (``*_dollars``); volume and open interest are
    ``*_fp`` strings. _market_to_event converts dollars -> cents (x100).
    """
    base: dict[str, Any] = {
        "ticker": "KXPRES-2028-DEM",
        "yes_bid_dollars": "0.4700",
        "yes_ask_dollars": "0.4900",
        "no_bid_dollars": "0.5100",
        "no_ask_dollars": "0.5300",
        "volume_fp": "12500.00",
        "open_interest_fp": "3200.00",
        "last_price_dollars": "0.4800",
    }
    base.update(overrides)
    return base


async def test_market_to_event_converts_valid_market() -> None:
    event = _market_to_event(_valid_market_dict())

    assert event is not None
    assert event.ticker == "KXPRES-2028-DEM"
    assert event.exchange == "kalshi"
    assert event.emitted_by == "data-svc"
    # Prices are dollars in the API, converted to cents (x100) by _market_to_event
    assert event.yes_bid == Decimal("47.00")
    assert event.yes_ask == Decimal("49.00")
    assert event.no_bid == Decimal("51.00")
    assert event.no_ask == Decimal("53.00")
    assert event.volume_24h == 12_500
    assert event.open_interest == 3_200
    assert event.last_trade_price == Decimal("48.00")


async def test_market_to_event_skips_empty_book() -> None:
    """Empty book on any side -> None, not Decimal('0'). Emitting 0 for
    a missing quote would look like a real price downstream — exactly
    the silent-data-quality failure Lesson 8 warns about."""
    # yes_bid_dollars = "0.0000" (empty bid side of yes — zero dollar price)
    assert _market_to_event(_valid_market_dict(yes_bid_dollars="0.0000")) is None
    # no_ask_dollars = None (field missing entirely)
    assert _market_to_event(_valid_market_dict(no_ask_dollars=None)) is None
    # All four sides need a quote — verify each fails individually
    for field in ("yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars"):
        assert _market_to_event(_valid_market_dict(**{field: "0.0000"})) is None


async def test_market_to_event_reads_volume_fp() -> None:
    """The live Kalshi API sends volume as volume_fp (a string).
    _market_to_event parses it to int via Decimal."""
    market = _valid_market_dict(volume_fp="7777.00")
    event = _market_to_event(market)
    assert event is not None
    assert event.volume_24h == 7_777

    # Missing volume_fp -> defaults to 0
    market = _valid_market_dict()
    del market["volume_fp"]
    event = _market_to_event(market)
    assert event is not None
    assert event.volume_24h == 0


async def test_poll_once_publishes_one_event_per_valid_market() -> None:
    """Three markets in (two valid, one with empty book) -> 2 published,
    1 skipped. publish_market_tick called exactly twice."""
    kalshi = AsyncMock()
    kalshi.list_markets = AsyncMock(return_value=[
        _valid_market_dict(ticker="GOOD-1"),
        _valid_market_dict(ticker="GOOD-2"),
        _valid_market_dict(ticker="BAD", yes_bid_dollars="0.0000"),
    ])
    publisher = AsyncMock()
    publisher.publish_market_tick = AsyncMock()

    published, skipped = await _poll_once(kalshi, publisher)

    assert published == 2
    assert skipped == 1
    assert publisher.publish_market_tick.await_count == 2
    # Verify the two published tickers (order preserved)
    published_tickers = [
        call.args[0].ticker
        for call in publisher.publish_market_tick.await_args_list
    ]
    assert published_tickers == ["GOOD-1", "GOOD-2"]


async def test_tick_poll_loop_cancels_cleanly() -> None:
    """Loop must propagate CancelledError so the task actually terminates
    on shutdown. If we swallow it, the lifespan finally block would hang
    forever waiting for a task that won't exit."""
    kalshi = AsyncMock()
    kalshi.list_markets = AsyncMock(return_value=[])
    publisher = AsyncMock()

    task = asyncio.create_task(
        tick_poll_loop(kalshi, publisher, interval_seconds=10)
    )
    # Let the loop start its first iteration.
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.done()
