from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    redis_url: str
    nats_url: str
    heartbeat_interval_seconds: int = 60
    service_name: str = "hello-svc"
