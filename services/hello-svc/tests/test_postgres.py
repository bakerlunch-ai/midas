import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from hello_svc.postgres import check_postgres


def test_check_postgres_calls_select_1_and_closes(settings_factory):
    conn = AsyncMock()
    conn.fetchval.return_value = 1

    with patch(
        "hello_svc.postgres.asyncpg.connect",
        new=AsyncMock(return_value=conn),
    ) as mock_connect:
        asyncio.run(check_postgres(settings_factory()))

    mock_connect.assert_awaited_once_with("postgresql://test/test")
    conn.fetchval.assert_awaited_once_with("SELECT 1")
    conn.close.assert_awaited_once()


def test_check_postgres_raises_on_unexpected_value(settings_factory):
    conn = AsyncMock()
    conn.fetchval.return_value = 42

    with (
        patch(
            "hello_svc.postgres.asyncpg.connect",
            new=AsyncMock(return_value=conn),
        ),
        pytest.raises(RuntimeError, match="42"),
    ):
        asyncio.run(check_postgres(settings_factory()))

    conn.close.assert_awaited_once()
