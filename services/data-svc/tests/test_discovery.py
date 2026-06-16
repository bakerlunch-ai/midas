"""Failing-first tests for data_svc.discovery (slow loop + universe holder)."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest
from data_svc.discovery import (
    SelectedUniverse,
    discover_once,
    discovery_loop,
)
from data_svc.market_selection import SelectionConfig


def _config() -> SelectionConfig:
    return SelectionConfig(
        named_series_prefixes=frozenset({"KXFED", "KXPRES"}),
        tight_max_spread_cents=Decimal("2"),
        tight_min_volume_24h=50,
        default_max_spread_cents=Decimal("5"),
        default_min_volume_24h=1000,
    )


def _market(ticker: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ticker": ticker,
        "yes_bid_dollars": "0.4700",
        "yes_ask_dollars": "0.4800",
        "no_bid_dollars": "0.5200",
        "no_ask_dollars": "0.5300",
        "volume_fp": "5000.00",
        "open_interest_fp": "1200.00",
        "last_price_dollars": "0.4750",
    }
    base.update(overrides)
    return base


# --- SelectedUniverse holder (pure, sync) ------------------------------

def test_selected_universe_snapshot_is_isolated_from_replace() -> None:
    universe = SelectedUniverse()
    universe.replace({"A", "B"})
    snap = universe.snapshot()
    universe.replace({"C"})
    assert snap == frozenset({"A", "B"})  # earlier snapshot unaffected
    assert universe.snapshot() == frozenset({"C"})


# --- discover_once -----------------------------------------------------

@pytest.mark.asyncio
async def test_discover_once_selects_only_passing_tickers() -> None:
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(return_value=[
        _market("KXFED-A"),                            # tight, passes
        _market("KXNBA-A", volume_fp="5000.00"),       # default, passes
        _market(  # dead book (both yes sides zero) -> no book, skipped
            "KXNBA-B", yes_bid_dollars="0.0000", yes_ask_dollars="0.0000"
        ),
    ])
    result = await discover_once(kalshi, _config())
    assert "KXFED-A" in result.selected
    assert "KXNBA-A" in result.selected
    assert "KXNBA-B" not in result.selected


@pytest.mark.asyncio
async def test_discover_once_excludes_skipped_tickers() -> None:
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(return_value=[
        _market("KXFED-LOWVOL", volume_fp="1.00"),  # below tight floor
    ])
    result = await discover_once(kalshi, _config())
    assert "KXFED-LOWVOL" not in result.selected
    assert result.selected == frozenset()


@pytest.mark.asyncio
async def test_discover_once_counts_selected_by_series() -> None:
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(return_value=[
        _market("KXFED-A"), _market("KXFED-B"),
        _market("KXPRES-A"),
        _market("KXNBA-A", volume_fp="5000.00"),
    ])
    result = await discover_once(kalshi, _config())
    assert result.by_series["KXFED"] == 2
    assert result.by_series["KXPRES"] == 1
    assert result.by_series["other"] == 1


@pytest.mark.asyncio
async def test_discover_once_paginates_all_open_markets() -> None:
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(return_value=[])
    await discover_once(kalshi, _config())
    kalshi.list_all_markets.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_once_returns_empty_when_no_markets_pass() -> None:
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(return_value=[
        _market(  # dead book (both yes sides zero) -> nothing passes
            "KXNBA-A", yes_bid_dollars="0.0000", yes_ask_dollars="0.0000"
        ),
    ])
    result = await discover_once(kalshi, _config())
    assert result.selected == frozenset()


# --- discovery_loop ----------------------------------------------------

@pytest.mark.asyncio
async def test_discovery_loop_replaces_universe_each_cycle() -> None:
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(return_value=[_market("KXFED-A")])
    universe = SelectedUniverse()
    task = asyncio.create_task(
        discovery_loop(kalshi, universe, _config(), interval_seconds=10)
    )
    await asyncio.sleep(0.05)  # let the first cycle run
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "KXFED-A" in universe.snapshot()


@pytest.mark.asyncio
async def test_discovery_loop_updates_shared_holder() -> None:
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(
        return_value=[_market("KXFED-A"), _market("KXPRES-B")]
    )
    universe = SelectedUniverse()
    task = asyncio.create_task(
        discovery_loop(kalshi, universe, _config(), interval_seconds=10)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert universe.snapshot() == frozenset({"KXFED-A", "KXPRES-B"})


@pytest.mark.asyncio
async def test_discovery_loop_logs_enriched_universe_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(return_value=[_market("KXFED-A")])
    universe = SelectedUniverse()
    with caplog.at_level(logging.INFO):
        task = asyncio.create_task(
            discovery_loop(kalshi, universe, _config(), interval_seconds=10)
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    msg = " ".join(r.message for r in caplog.records)
    assert "universe=" in msg
    assert "selected=" in msg


@pytest.mark.asyncio
async def test_discovery_loop_cancels_cleanly() -> None:
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(return_value=[])
    universe = SelectedUniverse()
    task = asyncio.create_task(
        discovery_loop(kalshi, universe, _config(), interval_seconds=10)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.done()


@pytest.mark.asyncio
async def test_discovery_loop_sleeps_first_when_seeded() -> None:
    """seeded=True: the caller already populated the universe, so the loop
    sleeps a full interval before its first scan. With interval=10s, a 50ms
    pause must see NO scan (vs the default seeded=False which scans at top)."""
    kalshi = AsyncMock()
    kalshi.list_all_markets = AsyncMock(return_value=[_market("KXFED-A")])
    universe = SelectedUniverse()
    task = asyncio.create_task(
        discovery_loop(kalshi, universe, _config(), interval_seconds=10, seeded=True)
    )
    await asyncio.sleep(0.05)  # well under the 10s interval
    kalshi.list_all_markets.assert_not_awaited()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.done()
