import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from app.models.base import AppBaseModel

if TYPE_CHECKING:
    from .user_model import Account


class Providers(str, Enum):
    GOOGLE = "google"
    GITHUB = "github"


class ProviderBase(AppBaseModel):
    provider: Providers
    provider_id: str
    scopes: Optional[str] = None
    expires_at: Optional[datetime] = None


class Provider(ProviderBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None

    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    account: "Account" = Relationship(back_populates="providers")
