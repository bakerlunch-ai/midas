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
from fastapi import FastAPI

from data_svc.kalshi_client import KalshiClient
from data_svc.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: settings → httpx → KalshiClient → Kalshi auth probe.
    Shutdown: close httpx."""
    settings = Settings()
    http_client = httpx.AsyncClient(timeout=15.0)
    kalshi = KalshiClient(
        api_key_id=settings.kalshi_api_key_id,
        private_key_pem=settings.kalshi_private_key_pem,
        base_url=settings.kalshi_base_url,
        http_client=http_client,
    )
    # Startup auth probe: one read call. Failure here crash-loops the pod
    # rather than running for hours with bad credentials.
    await kalshi.list_markets(limit=1)
    try:
        yield
    finally:
        await http_client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
