import redis.asyncio as redis
from redis.asyncio import Redis
from sqlmodel import create_engine

from app.common.constants import DATABASE_URI, REDIS_URL

# DB connection, session


def create_app_db_engine():
    return create_engine(DATABASE_URI)


redis_client: Redis = redis.from_url(
    REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)
