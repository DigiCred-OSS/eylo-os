"""Redis connection construction and lifecycle helpers."""

import redis.asyncio as redis

from eylo.common.config import settings


def get_redis_client(db: int | None = None) -> redis.Redis:
    """Get redis client for the "common" platform."""
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=db or settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
    )
