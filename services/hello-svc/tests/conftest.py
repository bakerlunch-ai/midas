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
