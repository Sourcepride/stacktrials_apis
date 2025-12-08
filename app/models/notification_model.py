import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

from app.models.base import AppBaseModelMixin, AppSQLModel

if TYPE_CHECKING:
    from .user_model import Account


class NotificationType(str):
    COURSE = "course"
    CHAT = "chat"
    COMMENT = "comment"
    RATING = "rating"
    SYSTEM = "system"
    INVITE = "invite"
    OTHER = "other"


class NotificationBase(AppSQLModel):
    type: str = Field(
        default=NotificationType.OTHER,
        index=True,
        description="Category of notification",
    )

    title: str = Field(max_length=255)
    message: str = Field(max_length=500)

    is_read: bool = Field(default=False, index=True)
    read_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )

    # Optional references to related objects
    # Example: course, chat, message, comment, rating...
    ref_id: Optional[str] = Field(
        default=None,
        index=True,
        description="Reference to related entity (UUID/short-id)",
    )
    ref_model: Optional[str] = Field(
        default=None, description="Model name of referenced object"
    )

    extra: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
        description="Flexible JSON storage for metadata",
    )


class Notification(AppBaseModelMixin, NotificationBase, table=True):
    __tablename__: str = "notification"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # The user receiving the notification
    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )

    account: "Account" = Relationship(back_populates="notifications")

    class Config:
        json_schema_extra = {
            "indexes": [
                {"fields": ["account_id", "is_read"]},
                {"fields": ["type"]},
                {"fields": ["ref_id", "ref_model"]},
            ]
        }
