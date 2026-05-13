from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from bot_events.base import BaseEvent


class PositionOpenedEvent(BaseEvent):
    """Emitted by pms-svc when a position becomes non-zero for the first time.

    Carried on NATS subject ``events.position.opened.<exchange>.<ticker>``.

    A position is the net holding for a given (exchange, ticker, side) tuple.
    pms-svc emits this when fills accumulate from net 0 → non-zero. Partial
    fills count — if a single OrderFilledEvent brings us from 0 contracts to
    60 contracts, the position is open at 60.

    ``opening_fill_id`` is the OrderFilledEvent.fill_id of the specific fill
    that crossed the 0-boundary. Audit trail for reconciliation.

    Position growth (adding to an existing open position) is NOT modeled as
    a separate event in v1 — replay the fill chain to derive current size.
    A future PositionUpdatedEvent may be added if downstream consumers need
    explicit signals.

    Prices in cents (Kalshi 0-100). Quantity always positive (direction is
    captured by ``side``, not by sign).
    """

    event_type = "position.opened"
    event_version = "1.0"

    exchange: Literal["kalshi"]
    ticker: str
    side: Literal["yes", "no"]

    position_id: UUID
    quantity: int = Field(gt=0)
    average_entry_price: Decimal = Field(ge=0, le=100)

    opened_at: datetime
    opening_fill_id: str
