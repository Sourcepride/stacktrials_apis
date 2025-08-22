import uuid

from pydantic import BaseModel

from app.models.user_model import AccountBase, Profile


class AccountRead(AccountBase):
    id: uuid.UUID
    profile: Profile


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    account: AccountRead
