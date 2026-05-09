import pytest

from hello_svc.config import Settings


@pytest.fixture
def settings_factory():
    """Build a Settings instance with sensible test defaults; pass overrides as kwargs."""

    def _factory(**overrides):
        base = {
            "database_url": "postgresql://test/test",
            "redis_url": "redis://test",
            "nats_url": "nats://test:4222",
        }
        return Settings(**(base | overrides))

    return _factory


@pytest.fixture
def env_settings(monkeypatch):
    """Set the env vars Settings() requires when lifespan instantiates it at startup."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test/test")
    monkeypatch.setenv("REDIS_URL", "redis://test")
    monkeypatch.setenv("NATS_URL", "nats://test:4222")
