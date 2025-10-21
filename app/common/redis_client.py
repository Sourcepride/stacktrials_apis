import redis.asyncio as aioredis

from app.common.constants import IS_DEV, REDIS_PASSWORD, REDIS_URL

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            password=None if IS_DEV else REDIS_PASSWORD,
            decode_responses=False,
        )
    return _redis
