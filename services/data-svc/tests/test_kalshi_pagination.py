"""Failing-first tests for KalshiClient pagination helpers.

list_all_markets    — follows Kalshi's cursor; caps at max_pages and warns
                      LOUDLY (naming what is truncated), never truncates silently.
list_markets_by_tickers — fetches an explicit ticker set, batched.

HTTP is mocked with httpx.MockTransport (same pattern as test_kalshi_client).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from data_svc.kalshi_client import KalshiClient

pytestmark = pytest.mark.asyncio

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


@pytest.fixture(scope="module")
def test_private_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")


def _client(http: httpx.AsyncClient, pem: str) -> KalshiClient:
    return KalshiClient(
        api_key_id="test-key-id",
        private_key_pem=pem,
        base_url=BASE_URL,
        http_client=http,
    )


def _markets(*tickers: str) -> list[dict[str, Any]]:
    return [{"ticker": t} for t in tickers]


# --- cursor following --------------------------------------------------

async def test_list_all_markets_follows_cursor_when_multiple_pages(
    test_private_pem: str,
) -> None:
    pages = [
        {"markets": _markets("A", "B"), "cursor": "page2"},
        {"markets": _markets("C"), "cursor": ""},
    ]
    seen_cursors: list[str | None] = []
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_cursors.append(request.url.params.get("cursor"))
        body = pages[calls["n"]]
        calls["n"] += 1
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = _client(http, test_private_pem)
        await client.list_all_markets()

    assert calls["n"] == 2
    assert "page2" in seen_cursors  # 2nd request carried the 1st page's cursor


async def test_list_all_markets_stops_when_cursor_empty(test_private_pem: str) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"markets": _markets("A"), "cursor": ""})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = _client(http, test_private_pem)
        await client.list_all_markets()

    assert calls["n"] == 1  # no second request once the cursor is empty


async def test_list_all_markets_returns_all_markets_across_pages(
    test_private_pem: str,
) -> None:
    pages = [
        {"markets": _markets("A", "B"), "cursor": "p2"},
        {"markets": _markets("C", "D"), "cursor": "p3"},
        {"markets": _markets("E"), "cursor": ""},
    ]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = pages[calls["n"]]
        calls["n"] += 1
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = _client(http, test_private_pem)
        markets = await client.list_all_markets()

    assert [m["ticker"] for m in markets] == ["A", "B", "C", "D", "E"]


async def test_list_all_markets_sends_page_size_limit_when_paginating(
    test_private_pem: str,
) -> None:
    seen_limits: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_limits.append(request.url.params.get("limit"))
        return httpx.Response(200, json={"markets": _markets("A"), "cursor": ""})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = _client(http, test_private_pem)
        await client.list_all_markets(page_size=1000)

    assert seen_limits[0] == "1000"


# --- max_pages safety cap (loud, not silent) ---------------------------

def _full_page_handler(page_size: int):
    """Every page is full (page_size markets) and always returns a non-empty
    cursor — i.e. it would paginate forever without the max_pages cap."""

    def handler(request: httpx.Request) -> httpx.Response:
        markets = _markets(*[f"T{i}" for i in range(page_size)])
        return httpx.Response(200, json={"markets": markets, "cursor": "more"})

    return handler


async def test_list_all_markets_logs_warning_when_max_pages_hit(
    test_private_pem: str, caplog: pytest.LogCaptureFixture
) -> None:
    transport = httpx.MockTransport(_full_page_handler(10))
    async with httpx.AsyncClient(transport=transport) as http:
        client = _client(http, test_private_pem)
        with caplog.at_level(logging.WARNING):
            await client.list_all_markets(page_size=10, max_pages=3)

    assert any("max_pages" in r.message for r in caplog.records)


async def test_list_all_markets_returns_partial_not_empty_when_capped(
    test_private_pem: str,
) -> None:
    transport = httpx.MockTransport(_full_page_handler(10))
    async with httpx.AsyncClient(transport=transport) as http:
        client = _client(http, test_private_pem)
        markets = await client.list_all_markets(page_size=10, max_pages=3)

    # 3 pages * 10 markets = 30 returned — capped, but NOT silently emptied.
    assert len(markets) == 30


async def test_list_all_markets_warning_names_truncation_count(
    test_private_pem: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The cap warning must NAME what is truncated: the page cap, the page
    size, and the count paginated so far (so the gap is observable)."""
    transport = httpx.MockTransport(_full_page_handler(10))
    async with httpx.AsyncClient(transport=transport) as http:
        client = _client(http, test_private_pem)
        with caplog.at_level(logging.WARNING):
            await client.list_all_markets(page_size=10, max_pages=3)

    msg = " ".join(r.message for r in caplog.records)
    assert "max_pages=3" in msg
    assert "page_size=10" in msg
    assert "30" in msg  # 3 * 10 paginated so far


# --- fetch by explicit ticker set, batched -----------------------------

async def test_list_markets_by_tickers_batches_when_over_batch_size(
    test_private_pem: str,
) -> None:
    seen_ticker_params: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        req = request.url.params.get("tickers") or ""
        seen_ticker_params.append(req)
        markets = _markets(*[t for t in req.split(",") if t])
        return httpx.Response(200, json={"markets": markets, "cursor": ""})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = _client(http, test_private_pem)
        tickers = [f"T{i}" for i in range(250)]
        markets = await client.list_markets_by_tickers(tickers, batch_size=100)

    assert len(seen_ticker_params) == 3  # 250 / 100 -> 3 requests
    assert len(markets) == 250


async def test_list_markets_by_tickers_returns_empty_when_no_tickers(
    test_private_pem: str,
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"markets": [], "cursor": ""})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = _client(http, test_private_pem)
        markets = await client.list_markets_by_tickers([], batch_size=100)

    assert markets == []
    assert calls["n"] == 0  # no HTTP call for an empty ticker set
