# Shared dependencies for routes


from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine
from sqlmodel import Session

from ..models.user_model import Account
from .database import create_app_db_engine
from .security import decode_token

engine = create_app_db_engine()
http_bearer = HTTPBearer()


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    token: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
    session: SessionDep,
):
    exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    values = decode_token(token.credentials)
    user_id = values.get("user_id")
    if not user_id:
        raise exception

    user = session.get(Account, user_id)

    if not user:
        raise exception

    return user


def get_current_active_user(
    current_user: Annotated["Account", Depends(get_current_user)],
):
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Inactive account")

    return current_user


CurrentActiveUser = Annotated["Account", Depends(get_current_active_user)]
