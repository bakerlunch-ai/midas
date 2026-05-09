import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import nats
from fastapi import FastAPI
from nats.aio.client import Client as NATSClient

from hello_svc.config import Settings
from hello_svc.heartbeat import publish_heartbeat
from hello_svc.postgres import check_postgres
from hello_svc.redis import check_redis


async def _heartbeat_loop(nc: NATSClient, settings: Settings) -> None:
    """Publish a heartbeat every settings.heartbeat_interval_seconds; exit on cancel."""
    try:
        while True:
            await publish_heartbeat(nc, settings)
            await asyncio.sleep(settings.heartbeat_interval_seconds)
    except asyncio.CancelledError:
        raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: settings → checks → NATS → heartbeat. Shutdown: cancel task → close NATS."""
    settings = Settings()
    await check_postgres(settings)
    await check_redis(settings)
    nc = await nats.connect(settings.nats_url)
    task = asyncio.create_task(_heartbeat_loop(nc, settings))
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await nc.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
