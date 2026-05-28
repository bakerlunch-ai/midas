"""Tick poller for data-svc.

Background task that periodically polls Kalshi /markets and publishes
each market as a MarketTickEvent on NATS. Runs as a single asyncio task
spawned by main.py's lifespan, cancelled cleanly on shutdown.

Design choices documented in commit message:
  - tick_at = datetime.now(UTC), because /markets has no broker timestamp.
    Carry item: replace with broker timestamp when we migrate to websocket.
  - Markets with missing or zero bid/ask are skipped, not emitted as 0.
    Lesson 8: don't fabricate data that looks real.
  - Volume field name falls back through three variants the legacy bot
    observed in production: "volume", "volume_24h", "volume_fp".
  - Per-market parse errors are logged and skipped; one bad market never
    kills the loop.
  - Top-level loop errors (Kalshi unreachable, NATS publish fails) are
    logged and the loop continues to the next sleep — same fail-loud-
    quietly pattern as hello-svc's heartbeat.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from bot_events.market_tick import MarketTickEvent

if TYPE_CHECKING:
    from data_svc.kalshi_client import KalshiClient
    from data_svc.nats_publisher import NATSPublisher

logger = logging.getLogger(__name__)

_EMITTED_BY = "data-svc"
_EXCHANGE = "kalshi"


def _dollars_to_cents(raw: Any) -> Decimal | None:
    """Parse a Kalshi dollar string to cents Decimal, or None on bad input."""
    if raw is None:
        return None
    try:
        return Decimal(str(raw)) * 100
    except (InvalidOperation, TypeError, ValueError):
        return None


def _fp_to_int(raw: Any) -> int:
    """Parse a Kalshi *_fp string to int, or 0 on bad input."""
    if raw is None:
        return 0
    try:
        return int(Decimal(str(raw)))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def _market_to_event(market: dict[str, Any]) -> MarketTickEvent | None:
    """Convert a Kalshi /markets dict to MarketTickEvent.

    Returns None if the market is missing required fields, has an empty
    book on any side, or fails Pydantic validation. The None path is
    expected and routine; the caller logs aggregate skip counts, not
    per-market warnings.

    The live Kalshi API sends prices as dollar strings with ``*_dollars``
    suffixed field names (e.g. ``yes_bid_dollars: "0.3830"``), volume and
    open interest as ``*_fp`` string fields. MarketTickEvent stores prices
    as Decimal cents (0-100), so we convert dollars * 100.
    """
    try:
        ticker = market.get("ticker")
        if not ticker:
            return None

        yes_bid = _dollars_to_cents(market.get("yes_bid_dollars"))
        yes_ask = _dollars_to_cents(market.get("yes_ask_dollars"))
        no_bid = _dollars_to_cents(market.get("no_bid_dollars"))
        no_ask = _dollars_to_cents(market.get("no_ask_dollars"))

        # Skip empty books — emitting Decimal("0") for a missing quote
        # is exactly the silent-data-quality failure Lesson 8 warns about.
        for px in (yes_bid, yes_ask, no_bid, no_ask):
            if px is None or px == 0:
                return None

        volume_24h = _fp_to_int(market.get("volume_fp"))
        open_interest = _fp_to_int(market.get("open_interest_fp"))
        last_price = _dollars_to_cents(market.get("last_price_dollars"))

        return MarketTickEvent(
            emitted_by=_EMITTED_BY,
            exchange=_EXCHANGE,
            ticker=ticker,
            tick_at=datetime.now(UTC),
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            no_bid=no_bid,
            no_ask=no_ask,
            volume_24h=volume_24h,
            open_interest=open_interest,
            last_trade_price=last_price,
        )
    except (KeyError, ValueError, TypeError, InvalidOperation, ValidationError):
        return None


async def _poll_once(
    kalshi: KalshiClient,
    publisher: NATSPublisher,
) -> tuple[int, int]:
    """Run one poll iteration. Returns (published, skipped)."""
    markets = await kalshi.list_markets()
    published = 0
    skipped = 0
    for market in markets:
        event = _market_to_event(market)
        if event is None:
            skipped += 1
            continue
        try:
            await publisher.publish_market_tick(event)
            published += 1
        except Exception:
            logger.exception("publish_market_tick raised; skipping market")
            skipped += 1
    return published, skipped


async def tick_poll_loop(
    kalshi: KalshiClient,
    publisher: NATSPublisher,
    interval_seconds: int,
) -> None:
    """Main poller loop. Spawned as a task by lifespan; cancelled on shutdown.

    Per-iteration exceptions are logged and the loop continues. Only
    CancelledError breaks out of the loop, which propagates so the task
    actually terminates on shutdown rather than swallowing the signal.
    """
    logger.info(
        "tick_poll_loop starting: interval=%ds", interval_seconds,
    )
    while True:
        try:
            published, skipped = await _poll_once(kalshi, publisher)
            logger.info(
                "poll cycle complete: published=%d skipped=%d",
                published, skipped,
            )
        except asyncio.CancelledError:
            logger.info("tick_poll_loop cancelled, exiting")
            raise
        except Exception:
            logger.exception("tick_poll_loop iteration raised; continuing")
        await asyncio.sleep(interval_seconds)
