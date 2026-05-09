import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from hello_svc.main import app


def test_lifespan_runs_checks_in_order_then_spawns_heartbeat(env_settings):
    calls: list[str] = []
    nats_client = AsyncMock()

    async def record_postgres(settings):
        calls.append("postgres")

    async def record_redis(settings):
        calls.append("redis")

    async def record_nats_connect(url):
        calls.append("nats_connect")
        return nats_client

    async def record_heartbeat(nc, settings):
        calls.append("heartbeat_loop")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise

    with (
        patch("hello_svc.main.check_postgres", record_postgres),
        patch("hello_svc.main.check_redis", record_redis),
        patch("hello_svc.main.nats.connect", record_nats_connect),
        patch("hello_svc.main._heartbeat_loop", record_heartbeat),
        TestClient(app) as client,
    ):
        response = client.get("/health")
        assert response.status_code == 200

    assert calls == ["postgres", "redis", "nats_connect", "heartbeat_loop"]


def test_lifespan_cancels_heartbeat_task_and_closes_nats_on_shutdown(env_settings):
    nats_client = AsyncMock()
    cancelled = False

    async def noop_check(settings):
        return None

    async def fake_nats_connect(url):
        return nats_client

    async def heartbeat_until_cancelled(nc, settings):
        nonlocal cancelled
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled = True
            raise

    with (
        patch("hello_svc.main.check_postgres", noop_check),
        patch("hello_svc.main.check_redis", noop_check),
        patch("hello_svc.main.nats.connect", fake_nats_connect),
        patch("hello_svc.main._heartbeat_loop", heartbeat_until_cancelled),
        TestClient(app) as client,
    ):
        client.get("/health")

    assert cancelled is True
    nats_client.close.assert_awaited_once()


def test_lifespan_propagates_check_failure_and_does_not_serve(env_settings):
    async def failing_postgres(settings):
        raise RuntimeError("postgres unreachable")

    with (
        patch("hello_svc.main.check_postgres", failing_postgres),
        pytest.raises(RuntimeError, match="postgres unreachable"),
        TestClient(app),
    ):
        pass
