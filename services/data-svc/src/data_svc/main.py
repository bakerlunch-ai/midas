"""data-svc FastAPI entrypoint.

Lifespan owns the httpx.AsyncClient + KalshiClient. Startup hits Kalshi once
(list_markets, limit=1) to fail loudly on bad credentials. No NATS publisher,
no Postgres, no Redis yet — those land in subsequent sessions.

Mirrors hello-svc/main.py shape:
- @asynccontextmanager lifespan, sequential startup, reverse-order shutdown
- Resources created inside lifespan(), closure-captured (not on app.state)
- /health = dumb liveness, returns {"ok": True} regardless of dependency state
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import nats
from fastapi import FastAPI

from data_svc.kalshi_client import KalshiClient
from data_svc.nats_publisher import NATSPublisher
from data_svc.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: settings -> httpx -> KalshiClient -> NATS -> probes.
    Shutdown: close NATS, close httpx (reverse order)."""
    settings = Settings()
    http_client = httpx.AsyncClient(timeout=15.0)
    kalshi = KalshiClient(
        api_key_id=settings.kalshi_api_key_id,
        private_key_pem=settings.kalshi_private_key_pem,
        base_url=settings.kalshi_base_url,
        http_client=http_client,
    )
    # NATS connect IS a startup fail-loud probe. If the broker is
    # unreachable, the pod crash-loops immediately instead of running
    # silently with no message bus. Mirrors hello-svc's pattern.
    nc = await nats.connect(settings.nats_url)
    publisher = NATSPublisher(nc)  # noqa: F841 — used by piece #4 (tick poller)
    # Startup auth probe: one Kalshi read call. Same fail-loud spirit.
    # Bad credentials crash-loop the pod instead of silent failure.
    await kalshi.list_markets(limit=1)
    try:
        yield
    finally:
        # Shutdown in reverse order of construction.
        await nc.close()
        await http_client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
