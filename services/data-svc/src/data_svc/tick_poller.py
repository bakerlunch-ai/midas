"""Tick poller for data-svc.

Fast loop (default 5s). Consults the SelectedUniverse maintained by the
discovery loop and fetches FRESH top-of-book quotes only for the selected
tickers, re-evaluating each against the selection rules at publish time so a
market that has gone thin since the last discovery cycle is skipped, not
published as junk. Each surviving market is published as a MarketTickEvent.

Design choices:
  - tick_at = datetime.now(UTC), because /markets has no broker timestamp.
    Carry item: replace with broker timestamp when we migrate to websocket.
  - Empty universe -> no-op cycle (logs published=0 skipped=0); the loop
    stays blind until discovery populates the universe.
  - Publishability is decided by is_publishable_book, shared with
    market_selection: a missing side (None) is missing data -> skip; a real 0
    is a truthful one-sided book (heavy favorite) -> publish. NO is mirror
    algebra (no_ask=100-yes_bid) and is DERIVED, never read from the dict.
  - Parsing helpers are shared with market_selection — one parse impl.
  - Top-level loop errors are logged and the loop continues. Only
    CancelledError breaks out (propagated for clean shutdown).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from bot_events.market_tick import MarketTickEvent
from data_svc.market_selection import (
    SelectionConfig,
    SkipReason,
    dollars_to_cents,
    evaluate,
    fp_to_int,
    is_publishable_book,
    summarize_skips,
)

if TYPE_CHECKING:
    from data_svc.discovery import SelectedUniverse
    from data_svc.kalshi_client import KalshiClient
    from data_svc.nats_publisher import NATSPublisher

logger = logging.getLogger(__name__)

_EMITTED_BY = "data-svc"
_EXCHANGE = "kalshi"
_CENTS_CEILING = Decimal("100")  # NO is mirror algebra: no_X = 100 - yes_X (cents)


def _market_to_event(market: dict[str, Any]) -> MarketTickEvent | None:
    """Convert a Kalshi /markets dict to MarketTickEvent, or None if the book
    is not publishable or Pydantic validation fails. The None path is expected
    and routine.

    The book is two real numbers, b=yes_bid and a=yes_ask (cents); the same
    is_publishable_book predicate evaluate() uses decides publishability
    (Lesson 5: one place). NO is mirror algebra and is DERIVED, never read from
    the dict: no_ask = 100 - yes_bid, no_bid = 100 - yes_ask. Deriving it means
    evaluate() and this function depend only on b,a and can never disagree, and
    every emitted event carries internally-consistent NO fields by construction.
    """
    try:
        ticker = market.get("ticker")
        if not ticker:
            return None
        yes_bid = dollars_to_cents(market.get("yes_bid_dollars"))
        yes_ask = dollars_to_cents(market.get("yes_ask_dollars"))
        if not is_publishable_book(yes_bid, yes_ask):
            return None
        assert yes_bid is not None and yes_ask is not None  # narrowed by guard
        return MarketTickEvent(
            emitted_by=_EMITTED_BY,
            exchange=_EXCHANGE,
            ticker=ticker,
            tick_at=datetime.now(UTC),
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            no_bid=_CENTS_CEILING - yes_ask,
            no_ask=_CENTS_CEILING - yes_bid,
            volume_24h=fp_to_int(market.get("volume_fp")),
            open_interest=fp_to_int(market.get("open_interest_fp")),
            last_trade_price=dollars_to_cents(market.get("last_price_dollars")),
        )
    except (KeyError, ValueError, TypeError, InvalidOperation, ValidationError):
        return None


async def _poll_once(
    kalshi: KalshiClient,
    publisher: NATSPublisher,
    universe: SelectedUniverse,
    config: SelectionConfig,
    batch_size: int = 100,
) -> tuple[int, dict[SkipReason, int]]:
    """Run one poll iteration over the selected universe.

    Returns ``(published_count, skip_reason_counts)``. An empty universe is a
    no-op: returns ``(0, {})`` without calling Kalshi. Otherwise fetch fresh
    quotes for the selected tickers, re-evaluate each, publish the passes, and
    count the skips by reason.
    """
    snap = universe.snapshot()
    if not snap:
        return 0, {}
    markets = await kalshi.list_markets_by_tickers(list(snap), batch_size=batch_size)
    published = 0
    results = []
    for market in markets:
        result = evaluate(market, config)
        results.append(result)
        if not result.passed:
            continue
        event = _market_to_event(market)
        if event is None:
            # evaluate passed but mapping failed (e.g. a price outside the
            # 0-100 schema range) — skip rather than publish a bad tick.
            continue
        try:
            await publisher.publish_market_tick(event)
            published += 1
        except Exception:
            logger.exception("publish_market_tick raised; skipping market")
    return published, summarize_skips(results)


async def tick_poll_loop(
    kalshi: KalshiClient,
    publisher: NATSPublisher,
    universe: SelectedUniverse,
    config: SelectionConfig,
    interval_seconds: int,
    batch_size: int = 100,
) -> None:
    """Main poller loop. Spawned as a task by lifespan; cancelled on shutdown.

    Per-iteration exceptions are logged and the loop continues. Only
    CancelledError breaks out, propagated so the task terminates on shutdown.
    """
    logger.info("tick_poll_loop starting: interval=%ds", interval_seconds)
    while True:
        try:
            published, skips = await _poll_once(
                kalshi, publisher, universe, config, batch_size
            )
            logger.info(
                "poll complete: published=%d skipped=%d "
                "(no_book=%d spread=%d volume=%d)",
                published,
                sum(skips.values()),
                skips.get(SkipReason.NO_BOOK, 0),
                skips.get(SkipReason.SPREAD_TOO_WIDE, 0),
                skips.get(SkipReason.VOLUME_TOO_LOW, 0),
            )
        except asyncio.CancelledError:
            logger.info("tick_poll_loop cancelled, exiting")
            raise
        except Exception:
            logger.exception("tick_poll_loop iteration raised; continuing")
        await asyncio.sleep(interval_seconds)
