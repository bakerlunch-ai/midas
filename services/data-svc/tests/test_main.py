"""Tests for data-svc main.py.

- /health endpoint returns {"ok": True} regardless of dependencies
- Startup probe runs exactly one Kalshi GET
- Startup connects to NATS exactly once
- Startup spawns tick_poll_loop with the configured interval
- Shutdown closes the httpx client and NATS connection (reverse order)
- Shutdown cancels the tick poller task
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def test_private_pem() -> str:
    """Throwaway RSA key so Settings() accepts the PEM at construction time."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")


@pytest.fixture
def env_with_kalshi(test_private_pem: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate DATA_SVC_* env vars so Settings() succeeds during lifespan."""
    monkeypatch.setenv("DATA_SVC_KALSHI_API_KEY_ID", "test-key-id")
    monkeypatch.setenv("DATA_SVC_KALSHI_PRIVATE_KEY_PEM", test_private_pem)
    monkeypatch.setenv(
        "DATA_SVC_KALSHI_BASE_URL",
        "https://api.elections.kalshi.com/trade-api/v2",
    )
    monkeypatch.setenv("DATA_SVC_NATS_URL", "nats://test-broker:4222")


@pytest.fixture
def mocked_nats():
    """Replace data_svc.main.nats.connect with an AsyncMock returning a
    fake NATS client. Yields (connect_mock, client_mock) so tests can
    assert on either."""
    client_mock = AsyncMock()
    client_mock.is_connected = True
    connect_mock = AsyncMock(return_value=client_mock)
    with patch("data_svc.main.nats.connect", connect_mock):
        yield connect_mock, client_mock


@pytest.fixture
def mocked_poller():
    """Replace data_svc.main.tick_poll_loop with an AsyncMock so lifespan
    tests don't spawn a real polling loop that would hammer the mocked
    Kalshi transport. Yields the mock so tests can assert on call args."""
    poller_mock = AsyncMock()
    with patch("data_svc.main.tick_poll_loop", poller_mock):
        yield poller_mock


def test_health_endpoint_returns_ok(
    env_with_kalshi: None, mocked_nats, mocked_poller
) -> None:
    """/health returns {"ok": True} without touching Kalshi after startup."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"markets": []})

    mocked = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=15.0)
    with patch("data_svc.main.httpx.AsyncClient", return_value=mocked):
        from data_svc.main import app
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"ok": True}


def test_lifespan_runs_startup_probe(
    env_with_kalshi: None, mocked_nats, mocked_poller
) -> None:
    """Startup runs exactly one list_markets call (fail-loud on bad creds)."""
    probe_calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        probe_calls.append(request)
        return httpx.Response(200, json={"markets": []})

    mocked = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=15.0)
    with patch("data_svc.main.httpx.AsyncClient", return_value=mocked):
        from data_svc.main import app
        with TestClient(app):
            pass

        assert len(probe_calls) == 1
        assert probe_calls[0].method == "GET"
        assert "/markets" in str(probe_calls[0].url)


def test_lifespan_closes_httpx_on_shutdown(
    env_with_kalshi: None, mocked_nats, mocked_poller
) -> None:
    """Shutdown calls aclose() on the httpx client."""
    aclose_mock = AsyncMock()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"markets": []})

    real_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=15.0)
    real_client.aclose = aclose_mock  # type: ignore[method-assign]

    with patch("data_svc.main.httpx.AsyncClient", return_value=real_client):
        from data_svc.main import app
        with TestClient(app):
            pass

        aclose_mock.assert_awaited_once()


def test_lifespan_connects_to_nats(
    env_with_kalshi: None, mocked_nats, mocked_poller
) -> None:
    """Startup calls nats.connect exactly once with the configured URL.
    NATS connect failure is a fail-loud startup probe — same spirit as
    the Kalshi auth probe. We assert the call happens; the failure path
    is exercised implicitly by lifespan propagating exceptions."""
    connect_mock, _ = mocked_nats

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"markets": []})

    mocked = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=15.0)
    with patch("data_svc.main.httpx.AsyncClient", return_value=mocked):
        from data_svc.main import app
        with TestClient(app):
            pass

        assert connect_mock.await_count == 1
        url_arg = connect_mock.await_args.args[0]
        assert url_arg == "nats://test-broker:4222"


def test_lifespan_closes_nats_on_shutdown(
    env_with_kalshi: None, mocked_nats, mocked_poller
) -> None:
    """Shutdown calls close() on the NATS client. Confirms the reverse-
    order shutdown ran the NATS half — pair with the httpx test above
    to confirm both halves of the lifespan close cleanly."""
    _, client_mock = mocked_nats

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"markets": []})

    mocked = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=15.0)
    with patch("data_svc.main.httpx.AsyncClient", return_value=mocked):
        from data_svc.main import app
        with TestClient(app):
            pass

        client_mock.close.assert_awaited_once()


def test_lifespan_spawns_tick_poller(
    env_with_kalshi: None, mocked_nats, mocked_poller
) -> None:
    """Startup calls tick_poll_loop exactly once with (kalshi, publisher,
    interval). Interval comes from settings.tick_poll_interval_seconds,
    default 5."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"markets": []})

    mocked = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=15.0)
    with patch("data_svc.main.httpx.AsyncClient", return_value=mocked):
        from data_svc.main import app
        with TestClient(app):
            pass

        mocked_poller.assert_called_once()
        args = mocked_poller.call_args.args
        # tick_poll_loop(kalshi, publisher, interval_seconds)
        assert len(args) == 3
        interval = args[2]
        assert interval == 5  # default from Settings


def test_lifespan_cancels_tick_poller_on_shutdown(
    env_with_kalshi: None, mocked_nats
) -> None:
    """Shutdown cancels the poller task. Uses a fake poller that sleeps
    indefinitely and observes its own CancelledError, so we can assert
    the cancel actually reached the task body — not just that the wrapping
    task was cancelled administratively."""
    cancelled: list[bool] = []

    async def fake_poller(*args, **kwargs) -> None:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"markets": []})

    mocked = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=15.0)
    with patch("data_svc.main.httpx.AsyncClient", return_value=mocked):
        with patch("data_svc.main.tick_poll_loop", fake_poller):
            from data_svc.main import app
            with TestClient(app):
                pass

    assert cancelled == [True]
