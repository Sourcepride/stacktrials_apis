import uuid
from typing import Optional

from pydantic import BaseModel

from app.models.user_model import AccountBase, Profile, ProfileBase


class AccountRead(AccountBase):
    id: uuid.UUID
    profile: Optional[Profile] = None


class RefreshToken(BaseModel):
    refresh_token: str


class AccessToken(BaseModel):
    access_token: str


class ShortLived(AccessToken):
    expires_in: int


class Token(AccessToken):
    refresh_token: str
    token_type: str
    expires_in: int
    account: AccountRead


class ProfileUpdate(ProfileBase):
    pass


class ProfileInformation(ProfileBase):
    id: uuid.UUID
    account_id: str
    username: str


class GoogleTokenPayload(BaseModel):
    credential: str
    redirect: Optional[str]
