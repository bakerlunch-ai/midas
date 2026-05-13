"""Kalshi API client — async, read-only, RSA-PSS signed.

Ported from the old bot's kalshi_client.py with three deliberate constraints:

1. ASYNC: uses httpx.AsyncClient, lifespan-managed by FastAPI
2. READ-ONLY: no _post method, no create_order, no get_balance,
   no get_positions, no get_orders. Cannot accidentally trade.
3. PRIVATE KEY FROM STRING: PEM-as-string (env var / sealed-secret),
   not a file path on disk.

Signature scheme (unchanged from old bot, matches Kalshi docs):
- payload = timestamp_ms + method + path (path includes /trade-api/v2)
- RSA-PSS with SHA256 hash, MGF1 SHA256, digest-length salt
- Base64-encoded signature in KALSHI-ACCESS-SIGNATURE header
"""

from __future__ import annotations

import base64
import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def _load_private_key_from_pem(pem_text: str) -> rsa.RSAPrivateKey:
    """Load an RSA private key from a PEM-formatted string."""
    return serialization.load_pem_private_key(
        pem_text.encode("utf-8"),
        password=None,
        backend=default_backend(),
    )


def _sign(private_key: rsa.RSAPrivateKey, text: str) -> str:
    """Sign text with RSA-PSS / SHA256 / MGF1-SHA256 / digest-length salt."""
    signature = private_key.sign(
        text.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


class KalshiClient:
    """Async, read-only Kalshi API client.

    Intentionally has no write methods. Adding one would require a
    deliberate code change visible in PR review. CI tests assert this.
    """

    def __init__(
        self,
        api_key_id: str,
        private_key_pem: str,
        base_url: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key_id = api_key_id
        self.base_url = base_url.rstrip("/")
        self._path_prefix = urlparse(self.base_url).path.rstrip("/")
        self._private_key = _load_private_key_from_pem(private_key_pem)
        # Allow injection for tests; otherwise caller manages lifecycle
        self._http = http_client

    def _headers(self, method: str, path: str) -> dict[str, str]:
        """Build the three Kalshi auth headers for a request."""
        ts = str(int(datetime.datetime.now(datetime.UTC).timestamp() * 1000))
        full_path = self._path_prefix + path
        full_path_no_query = full_path.split("?")[0]
        sig = _sign(self._private_key, ts + method + full_path_no_query)
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET a Kalshi endpoint. The ONLY HTTP verb this client uses."""
        if self._http is None:
            raise RuntimeError(
                "KalshiClient has no http_client; pass one via constructor or use as context manager"
            )
        url = self.base_url + path
        headers = self._headers("GET", path)
        resp = await self._http.get(url, headers=headers, params=params, timeout=15.0)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Read endpoints — public + portfolio reads
    # ------------------------------------------------------------------

    async def list_markets(
        self,
        status: str = "open",
        limit: int = 20,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        tickers: str | None = None,
    ) -> list[dict[str, Any]]:
        """List markets. /markets — paginated by Kalshi."""
        params: dict[str, Any] = {"status": status, "limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if tickers:
            params["tickers"] = tickers
        data = await self._get("/markets", params)
        return data.get("markets", [])

    async def get_market(self, ticker: str) -> dict[str, Any]:
        """Fetch a single market by ticker."""
        data = await self._get(f"/markets/{ticker}")
        return data.get("market", data)
