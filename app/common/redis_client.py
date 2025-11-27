from typing import Any

import redis.asyncio as aioredis

from app.common.constants import IS_DEV, REDIS_PASSWORD, REDIS_URL


def get_redis(**kwargs: Any) -> aioredis.Redis:
    kwargs.setdefault("decode_responses", False)

    return aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        password=None if IS_DEV else REDIS_PASSWORD,
        **kwargs,
    )
