import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bot_events import MarketTickEvent


def _valid_kwargs(**overrides):
    base = dict(
        emitted_by="data-svc",
        exchange="kalshi",
        ticker="PRES-2028-DEM",
        tick_at=datetime(2026, 5, 13, 2, 0, 0, tzinfo=UTC),
        yes_bid=Decimal("47"),
        yes_ask=Decimal("49"),
        no_bid=Decimal("51"),
        no_ask=Decimal("53"),
        last_trade_price=Decimal("48"),
        volume_24h=12_500,
        open_interest=3_200,
    )
    base.update(overrides)
    return base


def test_construction_with_required_fields_succeeds():
    ev = MarketTickEvent(**_valid_kwargs())
    assert ev.ticker == "PRES-2028-DEM"
    assert ev.exchange == "kalshi"


def test_event_type_and_version():
    ev = MarketTickEvent(**_valid_kwargs())
    assert type(ev).event_type == "market.tick"
    assert type(ev).event_version == "1.0"


def test_last_trade_price_is_optional():
    ev = MarketTickEvent(**_valid_kwargs(last_trade_price=None))
    assert ev.last_trade_price is None


def test_price_must_be_non_negative():
    with pytest.raises(ValidationError):
        MarketTickEvent(**_valid_kwargs(yes_bid=Decimal("-1")))


def test_price_must_be_at_most_one_hundred():
    with pytest.raises(ValidationError):
        MarketTickEvent(**_valid_kwargs(yes_ask=Decimal("101")))


def test_volume_must_be_non_negative():
    with pytest.raises(ValidationError):
        MarketTickEvent(**_valid_kwargs(volume_24h=-1))


def test_open_interest_must_be_non_negative():
    with pytest.raises(ValidationError):
        MarketTickEvent(**_valid_kwargs(open_interest=-1))


def test_unknown_exchange_rejected():
    with pytest.raises(ValidationError):
        MarketTickEvent(**_valid_kwargs(exchange="polymarket"))


def test_event_instance_is_frozen():
    ev = MarketTickEvent(**_valid_kwargs())
    with pytest.raises(ValidationError):
        ev.ticker = "OTHER"  # type: ignore[misc]


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        MarketTickEvent(**_valid_kwargs(unexpected_field=1))


def test_json_serialization_includes_class_constants():
    ev = MarketTickEvent(**_valid_kwargs())
    data = json.loads(ev.model_dump_json())
    assert data["event_type"] == "market.tick"
    assert data["event_version"] == "1.0"
    assert data["exchange"] == "kalshi"
    assert data["ticker"] == "PRES-2028-DEM"
    assert data["yes_bid"] == "47"  # Decimal serialized as string


def test_decimal_precision_preserved():
    ev = MarketTickEvent(**_valid_kwargs(yes_bid=Decimal("47.5")))
    data = json.loads(ev.model_dump_json())
    assert data["yes_bid"] == "47.5"
