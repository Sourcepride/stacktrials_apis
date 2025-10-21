import base64
import hashlib
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from cryptography.fernet import Fernet
from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.common.constants import SECRET_KEY
from app.common.enum import Providers
from app.models.base import AppBaseModelMixin, AppSQLModel

if TYPE_CHECKING:
    from .user_model import Account


fernet_key = base64.urlsafe_b64encode(
    hashlib.sha256((SECRET_KEY or "").encode()).digest()
)
fernet = Fernet(fernet_key)


def encrypt_token(token: str) -> str:
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(token_encrypted: str) -> str:
    return fernet.decrypt(token_encrypted.encode()).decode()


class ProviderBase(AppSQLModel):
    provider: Providers
    provider_id: str
    scopes: Optional[str] = None
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )


class Provider(AppBaseModelMixin, ProviderBase, table=True):
    __table_args__ = (
        UniqueConstraint("account_id", "provider", name="uix_account_provider"),
        UniqueConstraint("provider_id", "provider", name="uix_id_provider"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    access_token_encrypted: Optional[str] = None
    refresh_token_encrypted: Optional[str] = None

    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    account: "Account" = Relationship(back_populates="providers")

    @property
    def access_token(self) -> str | None:
        if self.access_token_encrypted:
            return decrypt_token(self.access_token_encrypted)
        return None

    @access_token.setter
    def access_token(self, value: str | None):
        if value:
            self.access_token_encrypted = encrypt_token(value)
        else:
            self.access_token_encrypted = None

    # --- refresh token ---
    @property
    def refresh_token(self) -> str | None:
        if self.refresh_token_encrypted:
            return decrypt_token(self.refresh_token_encrypted)
        return None

    @refresh_token.setter
    def refresh_token(self, value: str | None):
        if value:
            self.refresh_token_encrypted = encrypt_token(value)
        else:
            self.refresh_token_encrypted = None
