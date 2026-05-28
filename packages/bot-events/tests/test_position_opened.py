import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from bot_events import PositionOpenedEvent


def _valid_kwargs(**overrides):
    base = dict(
        emitted_by="pms-svc",
        exchange="kalshi",
        ticker="PRES-2028-DEM",
        side="yes",
        position_id=uuid4(),
        quantity=60,
        average_entry_price=Decimal("47"),
        opened_at=datetime(2026, 5, 13, 2, 30, 0, tzinfo=UTC),
        opening_fill_id="FILL-12345",
    )
    base.update(overrides)
    return base


def test_construction_with_required_fields_succeeds():
    ev = PositionOpenedEvent(**_valid_kwargs())
    assert ev.ticker == "PRES-2028-DEM"
    assert ev.side == "yes"
    assert ev.quantity == 60


def test_event_type_and_version():
    ev = PositionOpenedEvent(**_valid_kwargs())
    assert type(ev).event_type == "position.opened"
    assert type(ev).event_version == "1.0"


def test_no_side_position_supported():
    """A position can be on the NO side of a binary market."""
    ev = PositionOpenedEvent(**_valid_kwargs(side="no"))
    assert ev.side == "no"


def test_quantity_must_be_positive():
    """A position with zero quantity is not a position."""
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(quantity=0))


def test_quantity_must_not_be_negative():
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(quantity=-1))


def test_average_entry_price_must_be_non_negative():
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(average_entry_price=Decimal("-0.01")))


def test_average_entry_price_must_be_at_most_100():
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(average_entry_price=Decimal("100.5")))


def test_unknown_side_rejected():
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(side="both"))


def test_unknown_exchange_rejected():
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(exchange="polymarket"))


def test_position_id_must_be_uuid():
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(position_id="not-a-uuid"))


def test_event_instance_is_frozen():
    ev = PositionOpenedEvent(**_valid_kwargs())
    with pytest.raises(ValidationError):
        ev.quantity = 100  # type: ignore[misc]


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(unexpected_field=1))


def test_no_order_level_fields_present():
    """exchange_order_id intentionally not here — a position can be
    formed from multiple orders, can't pin to one."""
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(exchange_order_id="KX-1"))
    with pytest.raises(ValidationError):
        PositionOpenedEvent(**_valid_kwargs(limit_price=Decimal("48")))


def test_weighted_average_price_precision_preserved():
    """60@47 + 40@48 → avg = 47.4, must serialize cleanly."""
    ev = PositionOpenedEvent(**_valid_kwargs(
        quantity=100, average_entry_price=Decimal("47.4")
    ))
    data = json.loads(ev.model_dump_json())
    assert data["average_entry_price"] == "47.4"


def test_json_serialization_includes_class_constants():
    pid = uuid4()
    ev = PositionOpenedEvent(**_valid_kwargs(position_id=pid))
    data = json.loads(ev.model_dump_json())
    assert data["event_type"] == "position.opened"
    assert data["event_version"] == "1.0"
    assert data["position_id"] == str(pid)
    assert data["side"] == "yes"
    assert data["quantity"] == 60


def test_correlation_id_can_be_set():
    cid = uuid4()
    ev = PositionOpenedEvent(**_valid_kwargs(correlation_id=cid))
    assert ev.correlation_id == cid
