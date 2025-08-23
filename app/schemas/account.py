import uuid
from typing import Optional

from pydantic import BaseModel

from app.models.user_model import AccountBase, Profile, ProfileBase


class AccountRead(AccountBase):
    id: uuid.UUID
    profile: Optional[Profile] = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    account: AccountRead


class ProfileUpdate(ProfileBase):
    username: Optional[str] = None


class ProfileInformation(ProfileBase):
    id: uuid.UUID
    account_id: str
    username: str
