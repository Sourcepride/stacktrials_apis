import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Column, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from app.common.enum import AnnotationType
from app.models.base import AppBaseModelMixin, AppSQLModel

if TYPE_CHECKING:
    from .courses_model import DocumentContent
    from .user_model import Account


# ==============================
# DOCUMENT ANNOTATIONS
# ==============================
class DocumentAnnotationBase(AppSQLModel):
    type: AnnotationType = Field(description="note | highlight")
    page_number: Optional[int] = Field(default=None, ge=1)
    content: Optional[str] = Field(
        default=None, description="The note or highlighted text"
    )
    meta_data: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
        description="Additional info such as coordinates, color, style, etc.",
    )
    is_shared: bool = Field(
        default=False, description="Whether annotation is shared with others"
    )


class DocumentAnnotation(AppBaseModelMixin, DocumentAnnotationBase, table=True):
    __table_args__ = (
        Index("ix_document_page_type", "document_id", "page_number", "type"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID = Field(
        foreign_key="document_content.id", ondelete="CASCADE"
    )
    account_id: uuid.UUID = Field(foreign_key="account.id", ondelete="CASCADE")

    # Relationships
    document: "DocumentContent" = Relationship(back_populates="annotations")
    account: "Account" = Relationship(back_populates="document_annotations")


# ==============================
# DOCUMENT AI CHAT HISTORY
# ==============================
class DocumentChatBase(AppSQLModel):
    messages: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB),
        description="Array of messages in the chat: [{'role': 'user', 'content': ...}, ...]",
    )
    last_message_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC for ordering recent chats",
        ),
    )


class DocumentChat(AppBaseModelMixin, DocumentChatBase, table=True):
    __table_args__ = (Index("ix_document_chat_doc", "document_id", "account_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID = Field(
        foreign_key="document_content.id", ondelete="CASCADE"
    )
    account_id: uuid.UUID = Field(foreign_key="account.id", ondelete="CASCADE")

    # Relationships
    document: "DocumentContent" = Relationship(back_populates="chats")
    account: "Account" = Relationship(back_populates="document_chats")
