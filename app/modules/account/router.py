from typing import Annotated

from fastapi import APIRouter, Body

from app.core.dependencies import CurrentActiveUser, SessionDep
from app.modules.account.service import (
    delete_user_account,
    find_username,
    get_profile,
    my_account,
    update_current_profile,
    update_username,
)
from app.schemas.account import AccountRead, ProfileInformation, ProfileUpdate
from app.schemas.base import OkModel

router = APIRouter()


@router.get("/", response_model=AccountRead)
async def account(
    current_user: CurrentActiveUser,
    session: SessionDep,
):
    return await my_account(session, current_user)


@router.patch("/username", response_model=OkModel)
async def change_username(
    username: Annotated[str, Body()],
    current_user: CurrentActiveUser,
    session: SessionDep,
):
    return update_username(username, current_user, session)


@router.get("/username/exists", response_model=OkModel)
async def get_username(
    username: str,
    session: SessionDep,
):
    return await find_username(username, session)


@router.get("/{u}", response_model=ProfileInformation)
async def profile(u: str, session: SessionDep):
    return await get_profile(u, session)


@router.patch("/{u}", response_model=ProfileInformation)
async def update_profile(
    u: str,
    current_user: CurrentActiveUser,
    data: Annotated[ProfileUpdate, Body()],
    session: SessionDep,
):
    return await update_current_profile(u, current_user, data, session)


@router.delete("/{u}")
async def delete_account(current_user: CurrentActiveUser, session: SessionDep):
    return await delete_user_account(current_user, session)
