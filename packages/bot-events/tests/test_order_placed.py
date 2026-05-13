import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from bot_events import OrderPlacedEvent


def _valid_kwargs(**overrides):
    base = dict(
        emitted_by="oms-svc",
        exchange="kalshi",
        ticker="PRES-2028-DEM",
        client_order_id=uuid4(),
        exchange_order_id="KX-9876543",
        side="yes",
        direction="buy",
        quantity=100,
        limit_price=Decimal("48"),
    )
    base.update(overrides)
    return base


def test_construction_with_required_fields_succeeds():
    ev = OrderPlacedEvent(**_valid_kwargs())
    assert ev.ticker == "PRES-2028-DEM"
    assert ev.side == "yes"
    assert ev.direction == "buy"


def test_event_type_and_version():
    ev = OrderPlacedEvent(**_valid_kwargs())
    assert type(ev).event_type == "order.placed"
    assert type(ev).event_version == "1.0"


def test_order_type_defaults_to_limit():
    ev = OrderPlacedEvent(**_valid_kwargs())
    assert ev.order_type == "limit"


def test_time_in_force_defaults_to_gtc():
    ev = OrderPlacedEvent(**_valid_kwargs())
    assert ev.time_in_force == "GTC"


def test_quantity_must_be_positive():
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**_valid_kwargs(quantity=0))


def test_quantity_must_not_be_negative():
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**_valid_kwargs(quantity=-1))


def test_limit_price_must_be_non_negative():
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**_valid_kwargs(limit_price=Decimal("-0.01")))


def test_limit_price_must_be_at_most_100():
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**_valid_kwargs(limit_price=Decimal("100.5")))


def test_unknown_side_rejected():
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**_valid_kwargs(side="maybe"))


def test_unknown_direction_rejected():
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**_valid_kwargs(direction="hold"))


def test_unknown_time_in_force_rejected():
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**_valid_kwargs(time_in_force="GTD"))


def test_client_order_id_must_be_uuid():
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**_valid_kwargs(client_order_id="not-a-uuid"))


def test_exchange_order_id_is_required():
    kwargs = _valid_kwargs()
    del kwargs["exchange_order_id"]
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**kwargs)


def test_event_instance_is_frozen():
    ev = OrderPlacedEvent(**_valid_kwargs())
    with pytest.raises(ValidationError):
        ev.quantity = 200  # type: ignore[misc]


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        OrderPlacedEvent(**_valid_kwargs(unexpected_field=1))


def test_json_serialization_includes_class_constants():
    coid = uuid4()
    ev = OrderPlacedEvent(**_valid_kwargs(client_order_id=coid))
    data = json.loads(ev.model_dump_json())
    assert data["event_type"] == "order.placed"
    assert data["event_version"] == "1.0"
    assert data["client_order_id"] == str(coid)
    assert data["limit_price"] == "48"


def test_correlation_id_can_be_set():
    cid = uuid4()
    ev = OrderPlacedEvent(**_valid_kwargs(correlation_id=cid))
    assert ev.correlation_id == cid
