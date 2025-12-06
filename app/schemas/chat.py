import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.chat_model import (
    ChatBase,
    ChatInviteBase,
    ChatMemberBase,
    MessageBase,
    MessageReactionBase,
)
from app.models.user_model import AccountBase, ProfileBase
from app.schemas.base import CursorPaginationSchema, PaginatedSchema
from app.schemas.courses import CourseRead


class AccountRead(AccountBase):
    id: uuid.UUID
    profile: Optional["ProfileBase"] = None
    # Override email field to exclude it from serialization for security
    email: str = Field(exclude=True, repr=False)


class ChatRead(ChatBase):
    id: uuid.UUID
    account_id: Optional[uuid.UUID] = None
    course_id: Optional[str] = None

    course: Optional[CourseRead] = None
    account: Optional[AccountRead] = None

    model_config = ConfigDict(from_attributes=True)  # type: ignore


class ChatWrite(ChatBase):
    course_id: Optional[str] = None
    associate_account: Optional[str] = None


class ChatUpdate(ChatBase):
    pass


class ChatMemberRead(ChatMemberBase):
    id: uuid.UUID
    chat_id: uuid.UUID
    account_id: uuid.UUID
    last_read_message_id: Optional[uuid.UUID] = None
    is_creator: bool
    account: AccountRead
    created_at: datetime
    updated_at: datetime


class ChatMessageReactionRead(MessageReactionBase):
    id: uuid.UUID
    message_id: uuid.UUID
    account_id: uuid.UUID

    account: AccountRead


class ChatMessageRead(MessageBase):
    id: uuid.UUID
    chat_id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None
    reply_to_id: Optional[uuid.UUID] = None
    chat: ChatRead
    sender: Optional[ChatMemberRead] = None
    reply_to: Optional[MessageBase] = None
    # replies: list[MessageBase] = None
    reactions: list[ChatMessageReactionRead] = []
    model_config = ConfigDict(from_attributes=True)  # type: ignore
    created_at: datetime
    updated_at: datetime


class ChatMessageReadFromAttrs(ChatMemberRead):
    class Config:
        from_attributes = True


class ChatAndUnReadCount(BaseModel):
    chat: ChatRead
    unread_count: int
    has_reply: bool
    last_message: Optional[ChatMessageRead] = None


class PaginatedChatResp(PaginatedSchema):
    items: list[ChatAndUnReadCount]


class PaginatedPublicChatResp(PaginatedSchema):
    items: list[ChatRead]


class ChatMessageWrite(MessageBase):
    chat_id: uuid.UUID
    reply_to_id: Optional[uuid.UUID] = None


class ChatMessageUpdate(BaseModel):
    content: str


class ChatMessageReactionWrite(MessageReactionBase):
    pass


class PaginatedMessages(CursorPaginationSchema):
    items: list[ChatMessageRead]


class ChatInviteWrite(ChatInviteBase):
    chat_id: uuid.UUID
    invited_account_id: Optional[uuid.UUID] = None
    email: Optional[str] = None

    @model_validator(mode="after")
    def validate_email_or_account(self):
        """Either email or invited_account_id must be provided"""
        if not self.invited_account_id and not self.email:
            raise ValueError("Either email or invited_account_id must be provided")
        return self


class ChatInviteEmailWrite(BaseModel):
    """Schema for creating invites by email only (before user account exists)"""

    chat_id: uuid.UUID
    email: str = Field(..., description="Email address of the user to invite")
    max_uses: Optional[int] = Field(default=None, ge=1)
    expires_at: Optional[datetime] = None


class ChatInviteBulkWrite(BaseModel):
    data: list[ChatInviteWrite] = Field(
        ..., min_length=1, description="List of invites to create"
    )


class ChatInviteRead(ChatInviteBase):
    chat_id: uuid.UUID
    invited_account_id: Optional[uuid.UUID] = None
    email: Optional[str] = None
    chat: ChatRead
    invited_by: ChatMemberRead
    invited_account: Optional[AccountRead] = None


class PaginatedChatRead(PaginatedSchema):
    items: list[ChatRead]


class PaginatedChatReadWithUnReadCount(PaginatedSchema):
    items: list[ChatAndUnReadCount]


class PaginatedChatInviteRead(PaginatedSchema):
    items: list[ChatInviteRead]


class PaginatedChatMemberRead(PaginatedSchema):
    items: list[ChatMemberRead]
