"""data-svc FastAPI entrypoint.

Lifespan owns the httpx.AsyncClient + KalshiClient + NATS publisher and runs
TWO background loops:
  - discovery_loop (slow): paginates all open markets, maintains the selected
    universe.
  - tick_poll_loop (fast): publishes MarketTickEvents for the selected
    universe only.

Startup hits Kalshi once (list_markets, limit=1) to fail loudly on bad
credentials, connects to NATS (fail-loud), and — when
discovery_await_at_startup is true (default) — runs one discovery scan before
spawning the loops so the universe is populated immediately and a bad data
shape fails the pod at boot (Lesson 8 spirit).

Mirrors hello-svc/main.py shape: sequential startup, reverse-order shutdown,
resources closure-captured (not on app.state), /health = dumb liveness.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
import nats
from fastapi import FastAPI

from data_svc.discovery import SelectedUniverse, discover_once, discovery_loop
from data_svc.kalshi_client import KalshiClient
from data_svc.nats_publisher import NATSPublisher
from data_svc.settings import Settings
from data_svc.tick_poller import tick_poll_loop

# Configure root logger so application loggers (data_svc.*) emit to stdout.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: settings -> httpx -> KalshiClient -> NATS -> probes ->
    (optional) seed discovery -> spawn discovery + tick loops.
    Shutdown: cancel tick then discovery (LIFO), close NATS, close httpx."""
    settings = Settings()
    http_client = httpx.AsyncClient(timeout=15.0)
    kalshi = KalshiClient(
        api_key_id=settings.kalshi_api_key_id,
        private_key_pem=settings.kalshi_private_key_pem,
        base_url=settings.kalshi_base_url,
        http_client=http_client,
    )
    # NATS connect IS a startup fail-loud probe (unreachable broker -> crash).
    nc = await nats.connect(settings.nats_url)
    publisher = NATSPublisher(nc)
    # Startup auth probe: one Kalshi read. Bad credentials crash-loop the pod.
    await kalshi.list_markets(limit=1)

    selection_config = settings.selection_config()
    universe = SelectedUniverse()
    # Await-first (default): populate the universe before the tick loop runs,
    # and fail loud at boot if discovery raises. Escape hatch for ops:
    # DATA_SVC_DISCOVERY_AWAIT_AT_STARTUP=false spawns discovery in the
    # background and lets the tick loop no-op until the first scan lands.
    if settings.discovery_await_at_startup:
        result = await discover_once(kalshi, selection_config)
        universe.replace(result.selected)
        logger.info(
            "startup discovery seeded universe: selected=%d", len(result.selected)
        )

    discovery_task = asyncio.create_task(
        discovery_loop(
            kalshi,
            universe,
            selection_config,
            settings.discovery_interval_seconds,
            seeded=settings.discovery_await_at_startup,
        )
    )
    poller_task = asyncio.create_task(
        tick_poll_loop(
            kalshi,
            publisher,
            universe,
            selection_config,
            settings.tick_poll_interval_seconds,
            settings.tick_fetch_batch_size,
        )
    )
    try:
        yield
    finally:
        # Reverse-order (LIFO) shutdown: tick poller first, then discovery.
        poller_task.cancel()
        with suppress(asyncio.CancelledError):
            await poller_task
        discovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await discovery_task
        await nc.close()
        await http_client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
