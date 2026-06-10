"""Runtime settings for data-svc.

All fields populated from environment variables. Production secrets
(Kalshi API key, private key) come from sealed-secrets mounted as env vars.
Tunable policy (selection tiers, loop intervals) lives here, not in code
(Lesson 9).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from data_svc.market_selection import SelectionConfig, build_selection_config


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATA_SVC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    service_name: str = "data-svc"

    # Kalshi — RSA-PSS auth, read-only endpoints only
    kalshi_base_url: str = Field(
        default="https://api.elections.kalshi.com/trade-api/v2",
        description="Kalshi API base URL. Production by default; data-svc never calls write endpoints.",
    )
    kalshi_api_key_id: str = Field(
        default="",
        description="Kalshi API key ID (sealed-secret in cluster).",
    )
    kalshi_private_key_pem: str = Field(
        default="",
        description="Kalshi RSA private key, PEM format (sealed-secret in cluster).",
    )

    # NATS, Postgres, Redis
    nats_url: str = "nats://nats.nats.svc.cluster.local:4222"
    tick_poll_interval_seconds: int = 5
    postgres_dsn: str = ""
    redis_url: str = ""

    # --- Market selection: discovery loop (slow) ---
    discovery_interval_seconds: int = 60
    markets_page_size: int = 1000
    discovery_max_pages: int = 20
    discovery_await_at_startup: bool = True

    # --- Market selection: tick poll (fast) ---
    tick_fetch_batch_size: int = 100

    # --- Market selection: liquidity tiers (policy, Lesson 9) ---
    named_series_prefixes: Annotated[frozenset[str], NoDecode] = frozenset(
        {"KXFED", "KXPRES", "KXECON", "KXCPI", "KXINX", "KXHOUSERACE"}
    )
    tight_max_spread_cents: Decimal = Decimal("2")
    tight_min_volume_24h: int = 50
    default_max_spread_cents: Decimal = Decimal("5")
    default_min_volume_24h: int = 1000

    @field_validator("named_series_prefixes", mode="before")
    @classmethod
    def _split_csv_prefixes(cls, v: object) -> object:
        """Accept a comma-separated env string
        (DATA_SVC_NAMED_SERIES_PREFIXES="KXFED,KXPRES") as well as a real
        collection. NoDecode stops pydantic-settings from JSON-decoding the
        env value before this runs."""
        if isinstance(v, str):
            return frozenset(s.strip() for s in v.split(",") if s.strip())
        return v

    def selection_config(self) -> SelectionConfig:
        """Thin delegator to market_selection.build_selection_config, so all
        selection logic lives in one module and Settings stays plain config."""
        return build_selection_config(self)
