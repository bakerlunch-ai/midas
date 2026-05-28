from datetime import datetime
from typing import Literal

from pydantic import Field

from bot_events.base import BaseEvent

CancelReason = Literal[
    "user_requested",
    "market_closed",
    "expired",
    "market_settled",
    "exchange_other",
]


class OrderCancelledEvent(BaseEvent):
    """Emitted by oms-svc when an order is no longer active.

    Carried on NATS subject ``events.order.cancelled.<exchange>.<ticker>``.

    Terminal state for an order: after this fires, no further fills will
    occur on this exchange_order_id. A cancelled order MAY have partial
    fills — captured in ``final_filled_quantity``. The remaining quantity
    (original - final_filled_quantity) is derivable from OrderPlacedEvent.

    Semantic constraint (not enforced here, oms-svc's job): MUST NOT fire
    after the order is fully filled. A fully-filled order is already
    terminal; further cancel notifications from the exchange should be
    treated as duplicates and dropped upstream.
    """

    event_type = "order.cancelled"
    event_version = "1.0"

    exchange: Literal["kalshi"]
    ticker: str

    exchange_order_id: str
    cancelled_at: datetime
    reason: CancelReason
    final_filled_quantity: int = Field(ge=0, default=0)
