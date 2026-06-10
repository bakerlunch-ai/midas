"""Tests for data-svc TickPoller.

All tests use unittest.mock.AsyncMock for KalshiClient and NATSPublisher —
no real network, no real broker.

Covers:
- _market_to_event converts a valid Kalshi market dict (unchanged)
- _market_to_event skips markets with an empty book on any side (unchanged)
- _market_to_event falls back through the Kalshi volume field name (unchanged)
- _poll_once consults the SelectedUniverse: empty -> no-op; populated ->
  fetches ONLY the selected tickers, re-evaluates each fresh book, and
  aggregates skip-reason counts
- tick_poll_loop logs the enriched poll line and cancels cleanly
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest
from data_svc.discovery import SelectedUniverse
from data_svc.market_selection import SelectionConfig, SkipReason
from data_svc.tick_poller import (
    _market_to_event,
    _poll_once,
    tick_poll_loop,
)

# File-scoped marker — every test in this file is async (poller and its
# helpers are all coroutines). Same pattern as test_nats_publisher.py.
pytestmark = pytest.mark.asyncio


def _config() -> SelectionConfig:
    return SelectionConfig(
        named_series_prefixes=frozenset({"KXFED", "KXPRES"}),
        tight_max_spread_cents=Decimal("2"),
        tight_min_volume_24h=50,
        default_max_spread_cents=Decimal("5"),
        default_min_volume_24h=1000,
    )


def _valid_market_dict(**overrides: Any) -> dict[str, Any]:
    """Canonical valid Kalshi /markets dict for tests.

    Field names and values mirror the live Kalshi API (verified 2026-05-26).
    Prices are dollar strings (``*_dollars``); volume and open interest are
    ``*_fp`` strings. Default ticker is a named (tight-tier) series with a
    1c spread and ample volume, so it passes selection unless overridden.
    """
    base: dict[str, Any] = {
        "ticker": "KXFED-25DEC-T3.00",
        "yes_bid_dollars": "0.4700",
        "yes_ask_dollars": "0.4800",
        "no_bid_dollars": "0.5200",
        "no_ask_dollars": "0.5300",
        "volume_fp": "12500.00",
        "open_interest_fp": "3200.00",
        "last_price_dollars": "0.4800",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _market_to_event — mapping (behavior unchanged by market selection)
# ---------------------------------------------------------------------------

async def test_market_to_event_converts_valid_market() -> None:
    event = _market_to_event(_valid_market_dict(ticker="KXPRES-2028-DEM"))

    assert event is not None
    assert event.ticker == "KXPRES-2028-DEM"
    assert event.exchange == "kalshi"
    assert event.emitted_by == "data-svc"
    assert event.yes_bid == Decimal("47.00")
    assert event.yes_ask == Decimal("48.00")
    assert event.no_bid == Decimal("52.00")
    assert event.no_ask == Decimal("53.00")
    assert event.volume_24h == 12_500
    assert event.open_interest == 3_200
    assert event.last_trade_price == Decimal("48.00")


async def test_market_to_event_skips_empty_book() -> None:
    """Empty book on any side -> None, not Decimal('0') (Lesson 8)."""
    assert _market_to_event(_valid_market_dict(yes_bid_dollars="0.0000")) is None
    assert _market_to_event(_valid_market_dict(no_ask_dollars=None)) is None
    for field in (
        "yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars",
    ):
        assert _market_to_event(_valid_market_dict(**{field: "0.0000"})) is None


async def test_market_to_event_reads_volume_fp() -> None:
    """The live Kalshi API sends volume as volume_fp (a string)."""
    event = _market_to_event(_valid_market_dict(volume_fp="7777.00"))
    assert event is not None
    assert event.volume_24h == 7_777

    market = _valid_market_dict()
    del market["volume_fp"]
    event = _market_to_event(market)
    assert event is not None
    assert event.volume_24h == 0


# ---------------------------------------------------------------------------
# _poll_once — consults the selected universe, re-evaluates fresh books
# ---------------------------------------------------------------------------

async def test_poll_once_noops_when_selected_universe_empty() -> None:
    kalshi = AsyncMock()
    kalshi.list_markets_by_tickers = AsyncMock(return_value=[])
    publisher = AsyncMock()
    universe = SelectedUniverse()  # empty

    published, _skips = await _poll_once(kalshi, publisher, universe, _config())

    assert published == 0
    kalshi.list_markets_by_tickers.assert_not_awaited()
    publisher.publish_market_tick.assert_not_awaited()


async def test_poll_once_fetches_only_selected_tickers_when_populated() -> None:
    kalshi = AsyncMock()
    kalshi.list_markets_by_tickers = AsyncMock(
        return_value=[_valid_market_dict(ticker="KXFED-A")]
    )
    publisher = AsyncMock()
    universe = SelectedUniverse()
    universe.replace({"KXFED-A"})

    await _poll_once(kalshi, publisher, universe, _config())

    kalshi.list_markets_by_tickers.assert_awaited_once()
    called_tickers = kalshi.list_markets_by_tickers.await_args.args[0]
    assert set(called_tickers) == {"KXFED-A"}


async def test_poll_once_publishes_event_per_passing_selected_market() -> None:
    kalshi = AsyncMock()
    kalshi.list_markets_by_tickers = AsyncMock(return_value=[
        _valid_market_dict(ticker="KXFED-A"),
        _valid_market_dict(ticker="KXPRES-B"),
    ])
    publisher = AsyncMock()
    universe = SelectedUniverse()
    universe.replace({"KXFED-A", "KXPRES-B"})

    published, _skips = await _poll_once(kalshi, publisher, universe, _config())

    assert published == 2
    assert publisher.publish_market_tick.await_count == 2


async def test_poll_once_skips_and_counts_reason_when_selected_market_goes_illiquid() -> None:
    """A market selected last discovery cycle whose book is now empty must
    skip at publish time (re-evaluation), not be published as junk."""
    kalshi = AsyncMock()
    kalshi.list_markets_by_tickers = AsyncMock(return_value=[
        _valid_market_dict(ticker="KXFED-A", yes_bid_dollars="0.0000"),
    ])
    publisher = AsyncMock()
    universe = SelectedUniverse()
    universe.replace({"KXFED-A"})

    published, skips = await _poll_once(kalshi, publisher, universe, _config())

    assert published == 0
    assert skips[SkipReason.NO_BOOK] == 1
    publisher.publish_market_tick.assert_not_awaited()


async def test_poll_once_aggregates_skip_reason_counts() -> None:
    kalshi = AsyncMock()
    kalshi.list_markets_by_tickers = AsyncMock(return_value=[
        _valid_market_dict(ticker="KXFED-A", yes_bid_dollars="0.0000"),  # no_book
        _valid_market_dict(  # 5c spread > tight 2c -> spread
            ticker="KXFED-B", yes_bid_dollars="0.4000", yes_ask_dollars="0.4500",
        ),
        _valid_market_dict(ticker="KXFED-C", volume_fp="1.00"),  # volume too low
    ])
    publisher = AsyncMock()
    universe = SelectedUniverse()
    universe.replace({"KXFED-A", "KXFED-B", "KXFED-C"})

    published, skips = await _poll_once(kalshi, publisher, universe, _config())

    assert published == 0
    assert skips[SkipReason.NO_BOOK] == 1
    assert skips[SkipReason.SPREAD_TOO_WIDE] == 1
    assert skips[SkipReason.VOLUME_TOO_LOW] == 1


async def test_poll_once_batches_ticker_fetch_when_over_batch_size() -> None:
    """_poll_once delegates batching to list_markets_by_tickers; it must hand
    the full selected set through (the client chunks it)."""
    kalshi = AsyncMock()
    kalshi.list_markets_by_tickers = AsyncMock(return_value=[])
    publisher = AsyncMock()
    universe = SelectedUniverse()
    universe.replace({f"KXNBA-{i}" for i in range(250)})

    await _poll_once(kalshi, publisher, universe, _config())

    kalshi.list_markets_by_tickers.assert_awaited_once()
    passed = kalshi.list_markets_by_tickers.await_args.args[0]
    assert len(set(passed)) == 250


# ---------------------------------------------------------------------------
# tick_poll_loop — enriched logging + clean cancellation
# ---------------------------------------------------------------------------

async def test_tick_poll_loop_logs_enriched_poll_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    kalshi = AsyncMock()
    kalshi.list_markets_by_tickers = AsyncMock(
        return_value=[_valid_market_dict(ticker="KXFED-A")]
    )
    publisher = AsyncMock()
    universe = SelectedUniverse()
    universe.replace({"KXFED-A"})

    with caplog.at_level(logging.INFO):
        task = asyncio.create_task(
            tick_poll_loop(kalshi, publisher, universe, _config(), interval_seconds=10)
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    msg = " ".join(r.message for r in caplog.records)
    assert "published=" in msg
    assert "skipped=" in msg


async def test_tick_poll_loop_cancels_cleanly() -> None:
    """Loop must propagate CancelledError so the task actually terminates
    on shutdown. If we swallow it, the lifespan finally block would hang."""
    kalshi = AsyncMock()
    kalshi.list_markets_by_tickers = AsyncMock(return_value=[])
    publisher = AsyncMock()
    universe = SelectedUniverse()

    task = asyncio.create_task(
        tick_poll_loop(kalshi, publisher, universe, _config(), interval_seconds=10)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.done()
