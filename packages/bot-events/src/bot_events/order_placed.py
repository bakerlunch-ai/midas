from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from bot_events.base import BaseEvent


class OrderPlacedEvent(BaseEvent):
    """Emitted by oms-svc after the exchange acknowledges an order submission.

    Carried on NATS subject ``events.order.placed.<exchange>.<ticker>``.

    Emitted only after the exchange returns an acknowledgement and supplies
    an ``exchange_order_id``. If the submission fails before ack (e.g. auth,
    rate-limit, network), a separate rejection event is emitted instead.

    Prices in cents (Kalshi convention: 0-100). Quantity is in contracts.
    ``correlation_id`` (inherited) links this order back to the strategy
    decision or upstream event that triggered it.
    """

    event_type = "order.placed"
    event_version = "1.0"

    exchange: Literal["kalshi"]
    ticker: str

    client_order_id: UUID
    exchange_order_id: str

    side: Literal["yes", "no"]
    direction: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    limit_price: Decimal = Field(ge=0, le=100)

    order_type: Literal["limit"] = "limit"
    time_in_force: Literal["GTC", "IOC", "FOK"] = "GTC"
