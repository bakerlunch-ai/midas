"""Tests for data-svc NATSPublisher.

All tests use unittest.mock.AsyncMock for the NATS client — no real broker.

Covers:
- publish_market_tick writes to the right hierarchical subject
- payload is correctly serialized JSON matching MarketTickEvent schema
- publishing while disconnected raises RuntimeError (fail-loud, not silent)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from data_svc.nats_publisher import (
    MARKET_TICK_SUBJECT_PREFIX,
    NATSPublisher,
    market_tick_subject,
)

from bot_events.market_tick import MarketTickEvent

# File-scoped marker — every test in this file is async (NATSPublisher
# is an async collaborator). More explicit than repo-wide asyncio_mode.
pytestmark = pytest.mark.asyncio


def _sample_tick() -> MarketTickEvent:
    """Canonical valid MarketTickEvent for tests.

    Mirrors the working constructor in packages/bot-events/tests/test_market_tick.py.
    Prices are in cents (Kalshi convention, 0-100), NOT probabilities (0-1).
    """
    return MarketTickEvent(
        emitted_by="data-svc",
        exchange="kalshi",
        ticker="PRES-2028-DEM",
        tick_at=datetime(2026, 5, 13, 22, 0, 0, tzinfo=UTC),
        yes_bid=Decimal("47"),
        yes_ask=Decimal("49"),
        no_bid=Decimal("51"),
        no_ask=Decimal("53"),
        last_trade_price=Decimal("48"),
        volume_24h=12_500,
        open_interest=3_200,
    )


async def test_publish_market_tick_uses_hierarchical_subject() -> None:
    """Subject must be events.market.tick.<exchange>.<ticker> per the
    schema contract in packages/bot-events/market_tick.py docstring.
    Subscribers depend on this hierarchy for selective fanout."""
    nats_mock = AsyncMock()
    nats_mock.is_connected = True
    publisher = NATSPublisher(nats_mock)

    await publisher.publish_market_tick(_sample_tick())

    assert nats_mock.publish.await_count == 1
    subject = nats_mock.publish.await_args.args[0]
    assert subject == "events.market.tick.kalshi.PRES-2028-DEM"
    assert subject.startswith(MARKET_TICK_SUBJECT_PREFIX)
    assert subject == market_tick_subject(_sample_tick())


async def test_publish_market_tick_serializes_payload_as_json() -> None:
    nats_mock = AsyncMock()
    nats_mock.is_connected = True
    publisher = NATSPublisher(nats_mock)

    await publisher.publish_market_tick(_sample_tick())

    payload_bytes = nats_mock.publish.await_args.args[1]
    assert isinstance(payload_bytes, bytes)

    decoded = json.loads(payload_bytes.decode("utf-8"))
    assert decoded["ticker"] == "PRES-2028-DEM"
    assert decoded["exchange"] == "kalshi"
    assert decoded["emitted_by"] == "data-svc"
    # Pydantic serializes Decimal as string; the on-the-wire contract
    # is "47" not 47. If this assertion ever flips, the schema's
    # serialization convention has changed and downstream consumers
    # need to know.
    assert decoded["yes_bid"] == "47"


async def test_publish_raises_when_disconnected() -> None:
    """Fail-loud guard. Silent drops on a disconnected publisher would
    cause us to lose ticks without any signal — exactly the kind of
    invisible failure mode the old bot had (Lesson 8 territory)."""
    nats_mock = AsyncMock()
    nats_mock.is_connected = False
    publisher = NATSPublisher(nats_mock)

    with pytest.raises(RuntimeError, match="not connected"):
        await publisher.publish_market_tick(_sample_tick())

    assert nats_mock.publish.await_count == 0
