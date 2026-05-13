import json
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from bot_events import BankrollChangedEvent


def _valid_kwargs(**overrides):
    base = dict(
        emitted_by="pms-svc",
        amount_delta=Decimal("-50.00"),
        new_balance=Decimal("450.00"),
        change_reason="order_placed",
        source_event_id=uuid4(),
    )
    base.update(overrides)
    return base


def test_construction_with_required_fields_succeeds():
    ev = BankrollChangedEvent(**_valid_kwargs())
    assert ev.change_reason == "order_placed"
    assert ev.amount_delta == Decimal("-50.00")


def test_event_type_and_version():
    ev = BankrollChangedEvent(**_valid_kwargs())
    assert type(ev).event_type == "bankroll.changed"
    assert type(ev).event_version == "1.0"


def test_positive_delta_for_deposit():
    ev = BankrollChangedEvent(**_valid_kwargs(
        change_reason="deposit",
        amount_delta=Decimal("100.00"),
        new_balance=Decimal("500.00"),
        source_event_id=None,
    ))
    assert ev.amount_delta == Decimal("100.00")
    assert ev.source_event_id is None


def test_negative_delta_for_fee():
    ev = BankrollChangedEvent(**_valid_kwargs(
        change_reason="fee_paid",
        amount_delta=Decimal("-0.30"),
        new_balance=Decimal("449.70"),
    ))
    assert ev.amount_delta == Decimal("-0.30")


def test_position_settled_profit():
    ev = BankrollChangedEvent(**_valid_kwargs(
        change_reason="position_settled",
        amount_delta=Decimal("52.40"),
        new_balance=Decimal("502.40"),
    ))
    assert ev.change_reason == "position_settled"


def test_position_settled_loss():
    ev = BankrollChangedEvent(**_valid_kwargs(
        change_reason="position_settled",
        amount_delta=Decimal("-47.60"),
        new_balance=Decimal("402.40"),
    ))
    assert ev.amount_delta == Decimal("-47.60")


def test_negative_new_balance_allowed():
    """Reconciliation edge cases may produce negative balances transiently."""
    ev = BankrollChangedEvent(**_valid_kwargs(
        change_reason="manual_adjustment",
        amount_delta=Decimal("-500.00"),
        new_balance=Decimal("-50.00"),
        source_event_id=None,
    ))
    assert ev.new_balance == Decimal("-50.00")


def test_source_event_id_optional():
    """Deposits/withdrawals/manual_adjustments have no source event."""
    ev = BankrollChangedEvent(**_valid_kwargs(
        change_reason="deposit",
        amount_delta=Decimal("1000.00"),
        new_balance=Decimal("1450.00"),
        source_event_id=None,
    ))
    assert ev.source_event_id is None


def test_source_event_id_when_present_must_be_uuid():
    with pytest.raises(ValidationError):
        BankrollChangedEvent(**_valid_kwargs(source_event_id="not-a-uuid"))


def test_all_change_reasons_valid():
    reasons = [
        "deposit",
        "withdrawal",
        "order_placed",
        "order_cancelled",
        "fill_executed",
        "position_settled",
        "fee_paid",
        "manual_adjustment",
    ]
    for reason in reasons:
        ev = BankrollChangedEvent(**_valid_kwargs(change_reason=reason))
        assert ev.change_reason == reason


def test_unknown_change_reason_rejected():
    with pytest.raises(ValidationError):
        BankrollChangedEvent(**_valid_kwargs(change_reason="winnings"))


def test_event_instance_is_frozen():
    ev = BankrollChangedEvent(**_valid_kwargs())
    with pytest.raises(ValidationError):
        ev.new_balance = Decimal("9999")  # type: ignore[misc]


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        BankrollChangedEvent(**_valid_kwargs(unexpected_field=1))


def test_no_exchange_field():
    """Bankroll is bot-level, not exchange-level — no exchange/ticker fields."""
    with pytest.raises(ValidationError):
        BankrollChangedEvent(**_valid_kwargs(exchange="kalshi"))
    with pytest.raises(ValidationError):
        BankrollChangedEvent(**_valid_kwargs(ticker="X"))


def test_json_serialization_includes_class_constants():
    src = uuid4()
    ev = BankrollChangedEvent(**_valid_kwargs(source_event_id=src))
    data = json.loads(ev.model_dump_json())
    assert data["event_type"] == "bankroll.changed"
    assert data["event_version"] == "1.0"
    assert data["amount_delta"] == "-50.00"
    assert data["new_balance"] == "450.00"
    assert data["source_event_id"] == str(src)


def test_decimal_precision_preserved():
    ev = BankrollChangedEvent(**_valid_kwargs(
        amount_delta=Decimal("-0.0035"),
        new_balance=Decimal("449.9965"),
    ))
    data = json.loads(ev.model_dump_json())
    assert data["amount_delta"] == "-0.0035"
    assert data["new_balance"] == "449.9965"
