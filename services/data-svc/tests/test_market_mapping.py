"""Locks the real Kalshi /markets field mapping for _market_to_event.

Discovered at first deploy (2026-05-26): the deployed poller published 0
ticks because _market_to_event reads bare field names (yes_bid, no_ask,
volume, open_interest) but the live Kalshi API sends *_dollars / *_fp
suffixed names, AND sends prices as DOLLAR STRINGS ("0.3830") while our
MarketTickEvent schema stores CENTS as Decimal (38.30).

These tests are written against a real-shaped market dict captured from the
live API. They are EXPECTED TO FAIL until _market_to_event is fixed to:
  1. read the *_dollars / *_fp field names
  2. parse the string values
  3. convert dollars -> cents (multiply by 100)

This is the failing half of a test-first fix. The code change lands next
session as a separate PR (migration rule: behavioral changes get tests).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from data_svc.tick_poller import _market_to_event

import pytest

# These tests are a TEST-FIRST SPEC for the Kalshi field-mapping fix
# (next-session PR). They fail against current tick_poller.py by design.
# strict=True means: once the fix lands and they PASS, pytest reports
# xpass as a FAILURE — the signal to remove this marker. Until then the
# suite stays green and CI keeps gating.
pytestmark = pytest.mark.xfail(
    reason="Kalshi field mapping not yet fixed: API sends *_dollars/*_fp "
           "string fields; _market_to_event reads bare names. Fix is a "
           "separate tested PR (see commit adding this file).",
    strict=True,
)


def _real_kalshi_market(**overrides: Any) -> dict[str, Any]:
    """A market dict shaped like the LIVE Kalshi /markets response.

    Prices are dollar strings; volume/OI are *_fp strings. Mirrors the
    real fixture captured from the deployed pod on 2026-05-26.
    """
    base: dict[str, Any] = {
        "ticker": "KXTEST-26MAY26-T1",
        "status": "open",
        "yes_bid_dollars": "0.3830",
        "yes_ask_dollars": "0.4000",
        "no_bid_dollars": "0.6000",
        "no_ask_dollars": "0.6170",
        "last_price_dollars": "0.3900",
        "volume_fp": "1234.00",
        "open_interest_fp": "567.00",
    }
    base.update(overrides)
    return base


def test_maps_real_kalshi_market_to_event() -> None:
    """A live-shaped market must produce an event (not be skipped)."""
    event = _market_to_event(_real_kalshi_market())
    assert event is not None, (
        "live-shaped Kalshi market was skipped — _market_to_event is reading "
        "bare field names (yes_bid) instead of the real *_dollars names"
    )
    assert event.ticker == "KXTEST-26MAY26-T1"
    assert event.exchange == "kalshi"


def test_prices_converted_dollars_to_cents() -> None:
    """Kalshi dollar strings must become cents Decimal (x100)."""
    event = _market_to_event(_real_kalshi_market())
    assert event is not None
    # "0.3830" dollars -> 38.30 cents
    assert event.yes_bid == Decimal("38.30"), f"got {event.yes_bid}"
    assert event.yes_ask == Decimal("40.00"), f"got {event.yes_ask}"
    assert event.no_bid == Decimal("60.00"), f"got {event.no_bid}"
    assert event.no_ask == Decimal("61.70"), f"got {event.no_ask}"


def test_last_price_converted_to_cents() -> None:
    event = _market_to_event(_real_kalshi_market())
    assert event is not None
    # "0.3900" dollars -> 39.00 cents
    assert event.last_trade_price == Decimal("39.00"), f"got {event.last_trade_price}"


def test_volume_and_open_interest_parsed_from_fp_fields() -> None:
    """volume_fp / open_interest_fp strings must parse to ints."""
    event = _market_to_event(_real_kalshi_market())
    assert event is not None
    assert event.volume_24h == 1234, f"got {event.volume_24h}"
    assert event.open_interest == 567, f"got {event.open_interest}"


def test_prices_within_valid_cent_range() -> None:
    """After conversion, every price must be a valid 0-100 cent value.

    Guards against the 100x bug: if dollars aren't converted, a 0.38 stays
    0.38 (too low); if double-converted, 3830 (too high). Both wrong.
    """
    event = _market_to_event(_real_kalshi_market())
    assert event is not None
    for price in (event.yes_bid, event.yes_ask, event.no_bid, event.no_ask):
        assert Decimal("0") <= price <= Decimal("100"), (
            f"price {price} outside valid 0-100 cent range — unit conversion bug"
        )
