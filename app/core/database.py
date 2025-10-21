import redis.asyncio as redis
from redis.asyncio import Redis
from sqlmodel import create_engine

from app.common.constants import DATABASE_URI, IS_DEV, REDIS_PASSWORD, REDIS_URL

# DB connection, session


def create_app_db_engine():
    return create_engine(DATABASE_URI)


redis_client: Redis = redis.from_url(
    REDIS_URL,
    encoding="utf-8",
    password=None if IS_DEV else REDIS_PASSWORD,
    decode_responses=True,
)
