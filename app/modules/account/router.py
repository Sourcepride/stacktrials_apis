from typing import Annotated

from fastapi import APIRouter, Body

from app.core.dependencies import CurrentActiveUser
from app.modules.account.service import get_profile, update_current_profile
from app.schemas.account import ProfileInformation, ProfileUpdate

router = APIRouter()


@router.get("/{u}", response_model=ProfileInformation)
async def profile(u: str):
    return get_profile(u)


@router.patch("/{u}", response_model=ProfileInformation)
async def update_profile(
    u: str, current_user: CurrentActiveUser, data: Annotated[ProfileUpdate, Body()]
):
    return update_current_profile(u, current_user, data)


@router.delete("/{u}")
async def delete_account():
    pass
