import redis.asyncio as redis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import create_engine

from app.common.constants import (
    ASYNC_SUPPORT_DB_URI,
    DATABASE_URI,
    IS_DEV,
    REDIS_PASSWORD,
    REDIS_URL,
)

# DB connection, session


def create_sync_engine():
    return create_engine(DATABASE_URI)


def create_async__db_engine():
    return create_async_engine(ASYNC_SUPPORT_DB_URI, future=True, echo=False)


redis_client: Redis = redis.from_url(
    REDIS_URL,
    encoding="utf-8",
    password=None if IS_DEV else REDIS_PASSWORD,
    decode_responses=True,
)
