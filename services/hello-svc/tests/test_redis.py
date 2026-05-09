import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from hello_svc.redis import check_redis


def test_check_redis_calls_ping_and_closes(settings_factory):
    client = AsyncMock()
    client.ping.return_value = True

    with patch(
        "hello_svc.redis.Redis.from_url",
        return_value=client,
    ) as mock_from_url:
        asyncio.run(check_redis(settings_factory()))

    mock_from_url.assert_called_once_with("redis://test")
    client.ping.assert_awaited_once()
    client.aclose.assert_awaited_once()


def test_check_redis_raises_on_unexpected_response(settings_factory):
    client = AsyncMock()
    client.ping.return_value = "WRONG"

    with (
        patch("hello_svc.redis.Redis.from_url", return_value=client),
        pytest.raises(RuntimeError, match="WRONG"),
    ):
        asyncio.run(check_redis(settings_factory()))

    client.aclose.assert_awaited_once()
