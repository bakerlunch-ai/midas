from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from bot_events.base import BaseEvent


class OrderFilledEvent(BaseEvent):
    """Emitted by oms-svc when the exchange notifies of an order fill.

    Carried on NATS subject ``events.order.filled.<exchange>.<ticker>``.

    Kalshi orders can fill in multiple pieces. One event per fill
    notification. Consumers detect "fully filled" by comparing
    ``cumulative_filled_quantity`` to the original order quantity from
    the corresponding OrderPlacedEvent (joined via ``exchange_order_id``).

    Order-level facts (side, direction, limit_price) are NOT duplicated
    here — they live on OrderPlacedEvent and are joined via
    ``exchange_order_id`` to avoid event-sourcing contradictions.

    Prices in cents (0-100). Fees in dollars (not cents) — Kalshi charges
    per-contract dollar fees.
    """

    event_type = "order.filled"
    event_version = "1.0"

    exchange: Literal["kalshi"]
    ticker: str

    exchange_order_id: str
    fill_id: str

    fill_at: datetime
    fill_price: Decimal = Field(ge=0, le=100)
    filled_quantity: int = Field(gt=0)
    cumulative_filled_quantity: int = Field(gt=0)
    fees: Decimal = Field(ge=0)
