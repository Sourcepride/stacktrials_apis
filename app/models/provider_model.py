import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.common.enum import Providers
from app.models.base import AppBaseModelMixin

if TYPE_CHECKING:
    from .user_model import Account


class ProviderBase(SQLModel):
    provider: Providers
    provider_id: str
    scopes: Optional[str] = None
    expires_at: Optional[datetime] = None


class Provider(AppBaseModelMixin, ProviderBase, table=True):
    __table_args__ = (
        UniqueConstraint("account_id", "provider", name="uix_account_provider"),
        UniqueConstraint("provider_id", "provider", name="uix_id_provider"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None

    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    account: "Account" = Relationship(back_populates="providers")

    # TODO:  add unique constriant between  account_id and provider
