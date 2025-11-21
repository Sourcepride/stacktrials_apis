# Shared dependencies for routes


from typing import Annotated, AsyncGenerator, Optional

from fastapi import (
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketException,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.user_model import Account
from .database import create_async__db_engine, create_sync_engine, redis_client
from .security import decode_token

sync_engine = create_sync_engine()
async_engine = create_async__db_engine()
http_bearer = HTTPBearer(auto_error=False)

async_session = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session():
    async with async_session() as session:
        yield session


async def get_redis() -> AsyncGenerator:
    try:
        yield redis_client
    finally:
        # you usually don’t close it per request
        pass


SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def get_token_from_request(
    request: Request,
    bearer_token: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(http_bearer)
    ] = None,
):

    if bearer_token and bearer_token.credentials:
        return bearer_token.credentials

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    return ""


async def get_current_user(
    credentials: Annotated[str, Depends(get_token_from_request)],
    session: SessionDep,
):
    exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise exception

    values = decode_token(credentials)
    user_id = values.get("user_id")
    if not user_id:
        raise exception

    user = await session.get(Account, user_id)

    if not user:
        raise exception

    return user


async def get_current_user_silent(
    credentials: Annotated[Optional[str], Depends(get_token_from_request)],
    session: SessionDep,
):

    if not credentials:
        return

    values = decode_token(credentials)
    user_id = values.get("user_id")
    if not user_id:
        return

    user = await session.get(Account, user_id)

    if not user:
        return

    if not user.is_active:
        return

    return user


def get_current_active_user(
    current_user: Annotated["Account", Depends(get_current_user)],
):
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Inactive account")

    return current_user


async def get_current_user_ws(
    websocket: WebSocket,
    session: SessionDep,
    token: Annotated[str | None, Query()] = None,
):
    exception = WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    token = websocket.cookies.get("access_token") or token
    if not token:
        raise exception

    values = decode_token(token)
    user_id = values.get("user_id")

    if not user_id:
        raise exception

    user = await session.get(Account, user_id)

    if not user:
        raise exception

    return user


CurrentActiveUser = Annotated["Account", Depends(get_current_active_user)]
CurrentActiveUserSilent = Annotated[
    Optional["Account"], Depends(get_current_user_silent)
]
CurrentWSUser = Annotated[Account, Depends(get_current_user_ws)]
