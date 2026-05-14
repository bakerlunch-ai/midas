"""Tests for data-svc main.py.

- /health endpoint returns {"ok": True} regardless of dependencies
- Startup probe runs exactly one Kalshi GET
- Shutdown closes the httpx client
"""

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


def test_health_endpoint_returns_ok(env_with_kalshi: None) -> None:
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


def test_lifespan_runs_startup_probe(env_with_kalshi: None) -> None:
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


def test_lifespan_closes_httpx_on_shutdown(env_with_kalshi: None) -> None:
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
