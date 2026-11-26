from qdrant_client import AsyncQdrantClient
from redis.asyncio import ConnectionPool, Redis


def create_redis_pool(redis_url: str) -> ConnectionPool:
    """Create a bounded async Redis connection pool with explicit timeouts."""
    return ConnectionPool.from_url(
        redis_url,
        max_connections=50,
        socket_connect_timeout=2.0,
        socket_timeout=5.0,
        decode_responses=True,
    )


def create_redis_client(pool: ConnectionPool) -> Redis:
    """Create an async Redis client backed by the shared connection pool."""
    return Redis(connection_pool=pool)


def create_qdrant_client(qdrant_url: str) -> AsyncQdrantClient:
    """Create an async Qdrant client with a bounded request timeout."""
    return AsyncQdrantClient(url=qdrant_url, timeout=3)
