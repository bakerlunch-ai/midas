from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from bot_events.base import BaseEvent

CloseReason = Literal[
    "trade",
    "settled_yes",
    "settled_no",
]


class PositionClosedEvent(BaseEvent):
    """Emitted by pms-svc when a position's net quantity returns to 0.

    Carried on NATS subject ``events.position.closed.<exchange>.<ticker>``.

    Terminal state for a position. The ``position_id`` matches a prior
    PositionOpenedEvent — consumers join on it to compute holding period,
    cost basis history, etc.

    Three close reasons:

    - ``"trade"``: closing trades (opposing-side fills) brought net to 0.
      ``closing_fill_id`` will be the last fill that crossed the 0-boundary.

    - ``"settled_yes"``: the market resolved YES while we held the position.
      If we held the YES side, ``average_exit_price`` = 100 (Kalshi pays
      $1 per winning contract). If we held NO, ``average_exit_price`` = 0.
      ``closing_fill_id`` is None — settlement isn't a fill.

    - ``"settled_no"``: mirror of the above. YES holders get 0, NO holders
      get 100.

    ``realized_pnl`` is in DOLLARS (not cents), signed. Computed by pms-svc as:
      (average_exit_price - average_entry_price) * quantity * 0.01 - total_fees

    Pre-computed on the event so reporting/risk/learning consumers don't
    each have to replay the fill chain. pms-svc is the canonical source.
    """

    event_type = "position.closed"
    event_version = "1.0"

    exchange: Literal["kalshi"]
    ticker: str
    side: Literal["yes", "no"]

    position_id: UUID
    closed_at: datetime
    close_reason: CloseReason
    closing_fill_id: str | None = None

    original_quantity: int = Field(gt=0)
    average_entry_price: Decimal = Field(ge=0, le=100)
    average_exit_price: Decimal = Field(ge=0, le=100)

    total_fees: Decimal = Field(ge=0)
    realized_pnl: Decimal  # dollars, signed
