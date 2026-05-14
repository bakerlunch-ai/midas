"""Runtime settings for data-svc.

All fields populated from environment variables. Production secrets
(Kalshi API key, private key) come from sealed-secrets mounted as env vars.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # NATS, Postgres, Redis — same shape as hello-svc; will be wired next session
    nats_url: str = "nats://nats.nats.svc.cluster.local:4222"
    tick_poll_interval_seconds: int = 5
    postgres_dsn: str = ""
    redis_url: str = ""
