import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bot_events import OrderFilledEvent


def _valid_kwargs(**overrides):
    base = dict(
        emitted_by="oms-svc",
        exchange="kalshi",
        ticker="PRES-2028-DEM",
        exchange_order_id="KX-9876543",
        fill_id="FILL-12345",
        fill_at=datetime(2026, 5, 13, 2, 30, 0, tzinfo=UTC),
        fill_price=Decimal("47"),
        filled_quantity=60,
        cumulative_filled_quantity=60,
        fees=Decimal("0.30"),
    )
    base.update(overrides)
    return base


def test_construction_with_required_fields_succeeds():
    ev = OrderFilledEvent(**_valid_kwargs())
    assert ev.ticker == "PRES-2028-DEM"
    assert ev.filled_quantity == 60


def test_event_type_and_version():
    ev = OrderFilledEvent(**_valid_kwargs())
    assert type(ev).event_type == "order.filled"
    assert type(ev).event_version == "1.0"


def test_partial_fill_pattern():
    """Two partial fills: 60 then 40, cumulative tracks total."""
    first = OrderFilledEvent(**_valid_kwargs(
        fill_id="FILL-1", filled_quantity=60, cumulative_filled_quantity=60
    ))
    second = OrderFilledEvent(**_valid_kwargs(
        fill_id="FILL-2", filled_quantity=40, cumulative_filled_quantity=100
    ))
    assert first.cumulative_filled_quantity == 60
    assert second.cumulative_filled_quantity == 100


def test_filled_quantity_must_be_positive():
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(filled_quantity=0))


def test_filled_quantity_must_not_be_negative():
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(filled_quantity=-1))


def test_cumulative_must_be_positive():
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(cumulative_filled_quantity=0))


def test_fill_price_must_be_non_negative():
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(fill_price=Decimal("-0.01")))


def test_fill_price_must_be_at_most_100():
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(fill_price=Decimal("100.5")))


def test_fees_must_be_non_negative():
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(fees=Decimal("-0.01")))


def test_fees_zero_is_allowed():
    ev = OrderFilledEvent(**_valid_kwargs(fees=Decimal("0")))
    assert ev.fees == Decimal("0")


def test_unknown_exchange_rejected():
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(exchange="polymarket"))


def test_event_instance_is_frozen():
    ev = OrderFilledEvent(**_valid_kwargs())
    with pytest.raises(ValidationError):
        ev.fill_price = Decimal("50")  # type: ignore[misc]


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(unexpected_field=1))


def test_no_order_level_fields_present():
    """Side/direction/limit_price live on OrderPlacedEvent, not here.

    Sanity check: those fields should be rejected as extras.
    """
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(side="yes"))
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(direction="buy"))
    with pytest.raises(ValidationError):
        OrderFilledEvent(**_valid_kwargs(limit_price=Decimal("48")))


def test_json_serialization_includes_class_constants():
    ev = OrderFilledEvent(**_valid_kwargs())
    data = json.loads(ev.model_dump_json())
    assert data["event_type"] == "order.filled"
    assert data["event_version"] == "1.0"
    assert data["fill_price"] == "47"
    assert data["fees"] == "0.30"


def test_fees_decimal_precision_preserved():
    ev = OrderFilledEvent(**_valid_kwargs(fees=Decimal("0.0035")))
    data = json.loads(ev.model_dump_json())
    assert data["fees"] == "0.0035"
