import asyncpg

from hello_svc.config import Settings


async def check_postgres(settings: Settings) -> None:
    """Connect to Postgres, run SELECT 1, raise on failure."""
    conn = await asyncpg.connect(settings.database_url)
    try:
        result = await conn.fetchval("SELECT 1")
        if result != 1:
            raise RuntimeError(f"Postgres SELECT 1 returned {result!r}, expected 1")
    finally:
        await conn.close()
