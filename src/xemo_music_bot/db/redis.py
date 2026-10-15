"""Redis client construction.

Nothing here is a module-level global: the entrypoint builds one client at startup and
passes it to whatever needs it. Redis is a cache only (ADR 0004); nothing in it is the
source of truth.
"""

from redis.asyncio import Redis


def create_redis(url: str) -> Redis:
    """Create the application's Redis client, which keeps its own connection pool.

    Args:
        url: Redis URL, e.g. ``redis://127.0.0.1:6379/0``.

    Returns:
        A client that returns ``str`` instead of ``bytes``; the caller must
        ``await redis.aclose()`` on shutdown.
    """
    return Redis.from_url(url, decode_responses=True)


async def check_connection(redis: Redis) -> None:
    """Send ``PING`` to prove Redis is reachable.

    Args:
        redis: The client to check.

    Raises:
        redis.exceptions.RedisError: Redis rejected the connection, e.g. a wrong password.
        OSError: Redis is unreachable (refused, unknown host, timeout).
    """
    await redis.ping()
