from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from bot_events.base import BaseEvent


class MarketTickEvent(BaseEvent):
    """Emitted when a prediction market quote changes.

    Carried on NATS subject ``events.market.tick.<exchange>.<ticker>``.
    Prices are stored as Decimal in cents (Kalshi convention: 0-100 inclusive,
    where 50 = $0.50). The exchange's own timestamp is preserved in
    ``tick_at``; ``emitted_at`` (inherited) is when the bot observed it —
    the gap between the two is observable latency.

    For data-svc poll-mode (v1), the /markets endpoint does not carry a
    per-market broker timestamp; tick_at equals observation time. Will be
    replaced with broker timestamp when we migrate to websocket (carry item).
    """

    event_type = "market.tick"
    event_version = "1.0"

    exchange: Literal["kalshi"]
    ticker: str
    tick_at: datetime

    yes_bid: Decimal = Field(ge=0, le=100)
    yes_ask: Decimal = Field(ge=0, le=100)
    no_bid: Decimal = Field(ge=0, le=100)
    no_ask: Decimal = Field(ge=0, le=100)

    last_trade_price: Decimal | None = Field(default=None, ge=0, le=100)
    volume_24h: int = Field(ge=0)
    open_interest: int = Field(ge=0)
