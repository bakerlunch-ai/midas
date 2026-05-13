"""Tests for KalshiClient.

Three categories:
1. Signature/header shape — auth produces the right structure
2. Read-only guardrail — client cannot trade (no write methods exist)
3. Behavior — mocked GETs deserialize correctly
"""

import inspect
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import httpx
import pytest

from data_svc.kalshi_client import KalshiClient


# ----------------------------------------------------------------------
# Fixture: a real, throwaway RSA key for signature tests
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_private_pem() -> str:
    """Generate a test RSA key in-memory; never used against real Kalshi."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")


@pytest.fixture
def client(test_private_pem: str) -> KalshiClient:
    return KalshiClient(
        api_key_id="test-key-id",
        private_key_pem=test_private_pem,
        base_url="https://api.elections.kalshi.com/trade-api/v2",
    )


# ----------------------------------------------------------------------
# Signature / header shape
# ----------------------------------------------------------------------

def test_headers_include_three_kalshi_fields(client: KalshiClient) -> None:
    h = client._headers("GET", "/markets")
    assert "KALSHI-ACCESS-KEY" in h
    assert "KALSHI-ACCESS-SIGNATURE" in h
    assert "KALSHI-ACCESS-TIMESTAMP" in h
    assert h["Accept"] == "application/json"


def test_access_key_matches_constructor(client: KalshiClient) -> None:
    h = client._headers("GET", "/markets")
    assert h["KALSHI-ACCESS-KEY"] == "test-key-id"


def test_timestamp_is_milliseconds(client: KalshiClient) -> None:
    h = client._headers("GET", "/markets")
    assert h["KALSHI-ACCESS-TIMESTAMP"].isdigit()
    assert 13 <= len(h["KALSHI-ACCESS-TIMESTAMP"]) <= 14


def test_signature_is_base64(client: KalshiClient) -> None:
    h = client._headers("GET", "/markets")
    import base64
    decoded = base64.b64decode(h["KALSHI-ACCESS-SIGNATURE"])
    assert len(decoded) == 256  # 2048-bit RSA


def test_signature_changes_with_path(client: KalshiClient) -> None:
    h1 = client._headers("GET", "/markets")
    h2 = client._headers("GET", "/markets/PRES-2028")
    assert h1["KALSHI-ACCESS-SIGNATURE"] != h2["KALSHI-ACCESS-SIGNATURE"]


def test_signature_changes_with_method(client: KalshiClient) -> None:
    h_get = client._headers("GET", "/markets")
    h_post = client._headers("POST", "/markets")
    assert h_get["KALSHI-ACCESS-SIGNATURE"] != h_post["KALSHI-ACCESS-SIGNATURE"]


# ----------------------------------------------------------------------
# Read-only guardrail — the client must NEVER have write methods
# ----------------------------------------------------------------------

FORBIDDEN_METHOD_NAMES = {
    "create_order",
    "place_order",
    "cancel_order",
    "amend_order",
    "_post",
    "_put",
    "_patch",
    "_delete",
    "post",
    "put",
    "patch",
    "delete",
}


def test_no_write_methods_on_client() -> None:
    """If you're adding a write method to KalshiClient, you are in the wrong service.

    data-svc is read-only. Trading lives in oms-svc with separate credentials.
    """
    method_names = {
        name for name, _ in inspect.getmembers(KalshiClient, inspect.isfunction)
    }
    intersection = method_names & FORBIDDEN_METHOD_NAMES
    assert not intersection, f"forbidden write methods present: {intersection}"


def test_only_get_is_used_in_client_source() -> None:
    """Grep the client source: no httpx.AsyncClient.post / put / patch / delete calls."""
    import data_svc.kalshi_client as mod
    source = inspect.getsource(mod)
    for forbidden in (".post(", ".put(", ".patch(", ".delete("):
        assert forbidden not in source, (
            f"data-svc kalshi_client uses HTTP verb {forbidden!r}; "
            "this service is read-only"
        )


# ----------------------------------------------------------------------
# Behavior — mocked GETs
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_markets_returns_list(test_private_pem: str) -> None:
    """Mock httpx, assert list_markets unwraps the 'markets' key."""
    fake_response = {"markets": [{"ticker": "PRES-2028", "yes_bid": 47}]}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert "/markets" in str(request.url)
        assert request.headers["KALSHI-ACCESS-KEY"] == "test-key-id"
        return httpx.Response(200, json=fake_response)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = KalshiClient(
            api_key_id="test-key-id",
            private_key_pem=test_private_pem,
            base_url="https://api.elections.kalshi.com/trade-api/v2",
            http_client=http,
        )
        markets = await client.list_markets()
        assert markets == [{"ticker": "PRES-2028", "yes_bid": 47}]


@pytest.mark.asyncio
async def test_get_market_unwraps_market_key(test_private_pem: str) -> None:
    fake_response = {"market": {"ticker": "PRES-2028", "yes_bid": 47}}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json=fake_response)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = KalshiClient(
            api_key_id="test-key-id",
            private_key_pem=test_private_pem,
            base_url="https://api.elections.kalshi.com/trade-api/v2",
            http_client=http,
        )
        market = await client.get_market("PRES-2028")
        assert market == {"ticker": "PRES-2028", "yes_bid": 47}


@pytest.mark.asyncio
async def test_get_market_raises_on_http_error(test_private_pem: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = KalshiClient(
            api_key_id="test-key-id",
            private_key_pem=test_private_pem,
            base_url="https://api.elections.kalshi.com/trade-api/v2",
            http_client=http,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_market("NOPE")
