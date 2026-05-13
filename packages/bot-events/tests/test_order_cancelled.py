import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from bot_events import OrderCancelledEvent


def _valid_kwargs(**overrides):
    base = dict(
        emitted_by="oms-svc",
        exchange="kalshi",
        ticker="PRES-2028-DEM",
        exchange_order_id="KX-9876543",
        cancelled_at=datetime(2026, 5, 13, 2, 45, 0, tzinfo=UTC),
        reason="user_requested",
    )
    base.update(overrides)
    return base


def test_construction_with_required_fields_succeeds():
    ev = OrderCancelledEvent(**_valid_kwargs())
    assert ev.exchange_order_id == "KX-9876543"
    assert ev.reason == "user_requested"


def test_event_type_and_version():
    ev = OrderCancelledEvent(**_valid_kwargs())
    assert type(ev).event_type == "order.cancelled"
    assert type(ev).event_version == "1.0"


def test_final_filled_quantity_defaults_to_zero():
    ev = OrderCancelledEvent(**_valid_kwargs())
    assert ev.final_filled_quantity == 0


def test_partial_fill_then_cancel():
    ev = OrderCancelledEvent(**_valid_kwargs(final_filled_quantity=40))
    assert ev.final_filled_quantity == 40


def test_final_filled_quantity_must_be_non_negative():
    with pytest.raises(ValidationError):
        OrderCancelledEvent(**_valid_kwargs(final_filled_quantity=-1))


def test_final_filled_quantity_zero_is_allowed():
    ev = OrderCancelledEvent(**_valid_kwargs(final_filled_quantity=0))
    assert ev.final_filled_quantity == 0


def test_all_cancel_reasons_valid():
    for reason in [
        "user_requested",
        "market_closed",
        "expired",
        "market_settled",
        "exchange_other",
    ]:
        ev = OrderCancelledEvent(**_valid_kwargs(reason=reason))
        assert ev.reason == reason


def test_unknown_reason_rejected():
    with pytest.raises(ValidationError):
        OrderCancelledEvent(**_valid_kwargs(reason="just_because"))


def test_unknown_exchange_rejected():
    with pytest.raises(ValidationError):
        OrderCancelledEvent(**_valid_kwargs(exchange="polymarket"))


def test_event_instance_is_frozen():
    ev = OrderCancelledEvent(**_valid_kwargs())
    with pytest.raises(ValidationError):
        ev.reason = "expired"  # type: ignore[misc]


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        OrderCancelledEvent(**_valid_kwargs(unexpected_field=1))


def test_no_order_level_fields_present():
    """Side/direction/limit_price live on OrderPlacedEvent, not here."""
    with pytest.raises(ValidationError):
        OrderCancelledEvent(**_valid_kwargs(side="yes"))
    with pytest.raises(ValidationError):
        OrderCancelledEvent(**_valid_kwargs(limit_price="48"))


def test_json_serialization_includes_class_constants():
    ev = OrderCancelledEvent(**_valid_kwargs(final_filled_quantity=25))
    data = json.loads(ev.model_dump_json())
    assert data["event_type"] == "order.cancelled"
    assert data["event_version"] == "1.0"
    assert data["reason"] == "user_requested"
    assert data["final_filled_quantity"] == 25
