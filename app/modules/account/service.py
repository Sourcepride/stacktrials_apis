from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user_model import Account, Profile
from app.schemas.account import ProfileInformation, ProfileUpdate


async def my_account(session: AsyncSession, current_user: Account):
    # Reload account with profile to ensure it's available
    account = (
        await session.exec(
            select(Account)
            .where(Account.id == current_user.id)
            .options(selectinload(Account.profile))
        )
    ).first()

    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")

    return account


async def get_profile(u: str, session: AsyncSession):
    result = (
        await session.exec(
            select(Profile, Account.username).join(Account).where(Account.username == u)
        )
    ).first()

    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "username not found")

    profile, username = result

    if not username:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "username not found")

    return ProfileInformation(username=username, **jsonable_encoder(profile))


async def update_current_profile(
    username: str, current_user: Account, data: ProfileUpdate, session: AsyncSession
):
    result = (
        await session.exec(
            select(Profile, Account).join(Account).where(Account.username == username)
        )
    ).first()

    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user with username not found")

    profile, account = result

    if account.username != current_user.username:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "permission denied")

    cleaned_data = data.model_dump(exclude_unset=True)

    profile.sqlmodel_update(cleaned_data)
    session.add(profile)
    await session.commit()

    await session.refresh(profile)

    return ProfileInformation(username=username, **jsonable_encoder(profile))


async def update_username(username: str, current_user: Account, session: AsyncSession):
    username_taken = (
        await session.exec(select(Account).where(Account.username == username))
    ).first()

    if username_taken:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "username taken")

    current_user.username = username
    session.add(current_user)
    await session.commit()

    return {"ok": True}


async def find_username(username: str, session: AsyncSession):
    account = (
        await session.exec(select(Account).where(Account.username == username))
    ).first()

    return {"ok": bool(account)}


async def delete_user_account(current_user: Account, session: AsyncSession):
    await session.delete(current_user)
    await session.commit()
    return {"ok": True}
