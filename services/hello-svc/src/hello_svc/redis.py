from redis.asyncio import Redis

from hello_svc.config import Settings


async def check_redis(settings: Settings) -> None:
    """Connect to Redis, run PING, raise on failure."""
    client = Redis.from_url(settings.redis_url)
    try:
        response = await client.ping()
        if response not in (True, b"PONG", "PONG"):
            raise RuntimeError(f"Redis PING returned {response!r}, expected PONG")
    finally:
        await client.aclose()
