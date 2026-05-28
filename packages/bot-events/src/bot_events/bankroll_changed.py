from decimal import Decimal
from typing import Literal
from uuid import UUID

from bot_events.base import BaseEvent

ChangeReason = Literal[
    "deposit",
    "withdrawal",
    "order_placed",
    "order_cancelled",
    "fill_executed",
    "position_settled",
    "fee_paid",
    "manual_adjustment",
]


class BankrollChangedEvent(BaseEvent):
    """Emitted by pms-svc whenever available trading capital changes.

    Carried on NATS subject ``events.bankroll.changed``.

    Event-sourcing principle (binding constraint #1): there is NO mutable
    bankroll table. The current bankroll is the sum of all BankrollChangedEvent
    deltas. ``new_balance`` is included as a checksum and convenience — if you
    replay events and your sum differs from new_balance, you have a bug.

    ``amount_delta`` is signed in DOLLARS:
    - Positive: bankroll increased (deposit, profit, released reservation)
    - Negative: bankroll decreased (fee, loss, committed reservation)

    Change reasons (typed Literal):
    - deposit / withdrawal: external money in/out, source_event_id None
    - order_placed: cash reserved for open order's potential cost
    - order_cancelled: reservation released
    - fill_executed: order filled, reservation collapses into committed capital
    - position_settled: settlement payout (signed; loss is negative)
    - fee_paid: exchange fee deducted
    - manual_adjustment: reconciliation correction; source_event_id None

    ``source_event_id`` traces this change to the event that caused it
    (an OrderPlacedEvent, OrderFilledEvent, PositionClosedEvent, etc.).
    None for deposits/withdrawals/manual_adjustments which have no source.

    Note: ``new_balance`` is NOT constrained non-negative. Reconciliation
    errors or settlement timing can produce negative balances transiently;
    pms-svc raises alarms but the event type must be able to represent truth.
    """

    event_type = "bankroll.changed"
    event_version = "1.0"

    amount_delta: Decimal      # dollars, signed
    new_balance: Decimal       # dollars, signed (can go negative in edge cases)
    change_reason: ChangeReason
    source_event_id: UUID | None = None
