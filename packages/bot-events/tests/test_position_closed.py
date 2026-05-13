import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from bot_events import PositionClosedEvent


def _valid_kwargs(**overrides):
    base = dict(
        emitted_by="pms-svc",
        exchange="kalshi",
        ticker="PRES-2028-DEM",
        side="yes",
        position_id=uuid4(),
        closed_at=datetime(2026, 5, 13, 3, 0, 0, tzinfo=UTC),
        close_reason="trade",
        closing_fill_id="FILL-67890",
        original_quantity=100,
        average_entry_price=Decimal("47"),
        average_exit_price=Decimal("55"),
        total_fees=Decimal("0.60"),
        realized_pnl=Decimal("7.40"),  # (55-47) * 100 * 0.01 - 0.60 = 7.40
    )
    base.update(overrides)
    return base


def test_construction_with_required_fields_succeeds():
    ev = PositionClosedEvent(**_valid_kwargs())
    assert ev.ticker == "PRES-2028-DEM"
    assert ev.close_reason == "trade"
    assert ev.realized_pnl == Decimal("7.40")


def test_event_type_and_version():
    ev = PositionClosedEvent(**_valid_kwargs())
    assert type(ev).event_type == "position.closed"
    assert type(ev).event_version == "1.0"


def test_trade_close_has_closing_fill_id():
    ev = PositionClosedEvent(**_valid_kwargs(close_reason="trade"))
    assert ev.closing_fill_id == "FILL-67890"


def test_settlement_close_allows_null_closing_fill_id():
    """Settlement isn't a fill — closing_fill_id should be None."""
    ev = PositionClosedEvent(**_valid_kwargs(
        close_reason="settled_yes",
        closing_fill_id=None,
        average_exit_price=Decimal("100"),
        realized_pnl=Decimal("52.40"),
    ))
    assert ev.closing_fill_id is None
    assert ev.close_reason == "settled_yes"


def test_settlement_yes_with_yes_position_wins():
    """Held YES, market settled YES → exit at 100."""
    ev = PositionClosedEvent(**_valid_kwargs(
        side="yes",
        close_reason="settled_yes",
        closing_fill_id=None,
        average_entry_price=Decimal("47"),
        average_exit_price=Decimal("100"),
        realized_pnl=Decimal("52.40"),  # (100-47)*100*0.01 - 0.60
    ))
    assert ev.realized_pnl == Decimal("52.40")


def test_settlement_no_with_yes_position_loses():
    """Held YES, market settled NO → exit at 0, big loss."""
    ev = PositionClosedEvent(**_valid_kwargs(
        side="yes",
        close_reason="settled_no",
        closing_fill_id=None,
        average_entry_price=Decimal("47"),
        average_exit_price=Decimal("0"),
        realized_pnl=Decimal("-47.60"),  # (0-47)*100*0.01 - 0.60
    ))
    assert ev.realized_pnl == Decimal("-47.60")


def test_negative_pnl_is_allowed():
    """Losses must be representable — no constraint on pnl sign."""
    ev = PositionClosedEvent(**_valid_kwargs(realized_pnl=Decimal("-100")))
    assert ev.realized_pnl == Decimal("-100")


def test_original_quantity_must_be_positive():
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(original_quantity=0))


def test_average_entry_price_bounds():
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(average_entry_price=Decimal("-1")))
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(average_entry_price=Decimal("101")))


def test_average_exit_price_bounds():
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(average_exit_price=Decimal("-1")))
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(average_exit_price=Decimal("101")))


def test_total_fees_must_be_non_negative():
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(total_fees=Decimal("-0.01")))


def test_unknown_close_reason_rejected():
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(close_reason="rage_quit"))


def test_unknown_side_rejected():
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(side="maybe"))


def test_unknown_exchange_rejected():
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(exchange="polymarket"))


def test_event_instance_is_frozen():
    ev = PositionClosedEvent(**_valid_kwargs())
    with pytest.raises(ValidationError):
        ev.realized_pnl = Decimal("999")  # type: ignore[misc]


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        PositionClosedEvent(**_valid_kwargs(unexpected_field=1))


def test_json_serialization_includes_class_constants():
    pid = uuid4()
    ev = PositionClosedEvent(**_valid_kwargs(position_id=pid))
    data = json.loads(ev.model_dump_json())
    assert data["event_type"] == "position.closed"
    assert data["event_version"] == "1.0"
    assert data["position_id"] == str(pid)
    assert data["close_reason"] == "trade"
    assert data["realized_pnl"] == "7.40"


def test_pnl_decimal_precision_preserved():
    """Tiny pnl shouldn't lose precision when round-tripping JSON."""
    ev = PositionClosedEvent(**_valid_kwargs(realized_pnl=Decimal("0.0125")))
    data = json.loads(ev.model_dump_json())
    assert data["realized_pnl"] == "0.0125"
