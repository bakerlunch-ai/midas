"""NATS publisher for data-svc.

Owns publishing semantics only, not the connection itself. The NATS
client is injected (same shape as KalshiClient takes httpx.AsyncClient),
so the lifespan owns connection lifecycle and tests can swap in a fake.

Subject naming follows the contract documented in
packages/bot-events/src/bot_events/market_tick.py:

    events.market.tick.<exchange>.<ticker>

This lets subscribers filter at the broker level:
- risk-svc could subscribe events.market.tick.kalshi.>
- a KXPRES-only strategy could subscribe events.market.tick.kalshi.KXPRES-*
- pms-svc reads everything via events.market.tick.>
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bot_events.market_tick import MarketTickEvent

if TYPE_CHECKING:
    from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)

MARKET_TICK_SUBJECT_PREFIX = "events.market.tick"


def market_tick_subject(event: MarketTickEvent) -> str:
    """Build the NATS subject for a MarketTickEvent.

    Returns: events.market.tick.<exchange>.<ticker>
    """
    return f"{MARKET_TICK_SUBJECT_PREFIX}.{event.exchange}.{event.ticker}"


class NATSPublisher:
    """Publishes data-svc events onto NATS subjects.

    Does NOT own the NATS connection. The connection is created and closed
    in the FastAPI lifespan; the publisher just holds a reference.
    """

    def __init__(self, nats_client: NATSClient) -> None:
        self._nats = nats_client

    async def publish_market_tick(self, event: MarketTickEvent) -> None:
        """Publish a MarketTickEvent to its exchange/ticker subject.

        Serialization: Pydantic .model_dump_json() — already the canonical
        wire format defined in packages/bot-events/.
        """
        if not self._nats.is_connected:
            raise RuntimeError(
                "NATSPublisher cannot publish: NATS client is not connected. "
                "Connection lifecycle is owned by the FastAPI lifespan; "
                "this indicates startup failed or shutdown ran early."
            )

        subject = market_tick_subject(event)
        payload = event.model_dump_json().encode("utf-8")
        await self._nats.publish(subject, payload)
        logger.debug(
            "Published MarketTickEvent to %s: ticker=%s",
            subject,
            event.ticker,
        )
