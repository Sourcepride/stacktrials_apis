import uuid
from typing import Optional

from pydantic import BaseModel

from app.models.chat_model import (
    ChatBase,
    ChatInviteBase,
    ChatMemberBase,
    MessageBase,
    MessageReactionBase,
)
from app.schemas.account import AccountRead
from app.schemas.base import PaginatedSchema
from app.schemas.courses import CourseRead


class ChatRead(ChatBase):
    id: uuid.UUID
    account_id: Optional[uuid.UUID] = None
    course_id: Optional[str] = None

    course: Optional[CourseRead] = None
    account: Optional[AccountRead] = None


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
    is_admin: bool
    is_creator: bool
    account: AccountRead


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


class ChatAndUnReadCount(BaseModel):
    chat: ChatRead
    unread_count: int
    has_reply: bool


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


class PaginatedMessages(PaginatedSchema):
    items: list[ChatMessageRead]


class ChatInviteWrite(ChatInviteBase):
    chat_id: uuid.UUID
    invited_account_id: uuid.UUID


class ChatInviteRead(ChatInviteBase):
    chat_id: uuid.UUID
    invited_account_id: uuid.UUID
    chat: ChatRead
    invited_by: ChatMemberRead
    invited_account: AccountRead
