import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from app.common.enum import (
    ChatType,
    GroupChatPrivacy,
    MemberRole,
    MemberStatus,
    MessageType,
)
from app.models.base import AppBaseModelMixin, AppSQLModel

if TYPE_CHECKING:
    from .courses_model import Course
    from .user_model import Account


class ChatBase(AppSQLModel):
    chat_type: ChatType = Field(index=True)
    name: Optional[str] = Field(max_length=255, default=None)  # For group chats
    description: Optional[str] = None  # For group chats
    avatar_url: Optional[str] = Field(max_length=500, default=None)
    privacy: Optional[GroupChatPrivacy] = Field(
        index=True, default=None
    )  # Only for group chats
    is_active: bool = Field(default=True)
    max_members: Optional[int] = Field(default=None, ge=2, le=50)


class Chat(AppBaseModelMixin, ChatBase, table=True):

    __table_args__ = (Index("ix_privacy_active", "privacy", "is_active"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    account_id: Optional[uuid.UUID] = Field(
        foreign_key="account.id", ondelete="SET NULL", index=True, default=None
    )  # User who created the chat
    course_id: Optional[str] = Field(
        foreign_key="course.id", default=None, ondelete="SET NULL"
    )  # Optional course association

    # Relationships
    course: Optional["Course"] = Relationship(back_populates="chats")
    account: Optional["Account"] = Relationship(back_populates="created_chats")
    messages: list["Message"] = Relationship(back_populates="chat", cascade_delete=True)
    members: list["ChatMember"] = Relationship(
        back_populates="chat", passive_deletes="all"
    )

    # Indexes
    class Config:
        json_schema_extra = {
            "indexes": [
                {"fields": ["chat_type"]},
                {"fields": ["privacy"]},
                {"fields": ["course_id"]},
                {"fields": ["account"]},
                {"fields": ["is_active"]},
            ]
        }


class ChatMemberBase(AppSQLModel):
    role: MemberRole = Field(default=MemberRole.MEMBER)
    status: MemberStatus = Field(default=MemberStatus.ACTIVE)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    left_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )
    notifications_enabled: bool = Field(default=True)
    is_pinned: bool = Field(default=False)  # Pin chat for user


class ChatMember(AppBaseModelMixin, ChatMemberBase, table=True):
    __tablename__: str = "chat_member"

    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", name="uix_account_chat"),
        Index("ix_account_status", "account_id", "status"),
        Index("ix_chat_role", "chat_id", "role"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chat_id: uuid.UUID = Field(foreign_key="chat.id", index=True, ondelete="CASCADE")
    account_id: uuid.UUID = Field(
        foreign_key="account.id", ondelete="CASCADE", index=True
    )
    last_read_message_id: Optional[uuid.UUID] = Field(
        default=None,
    )

    # Relationships
    chat: Chat = Relationship(back_populates="members")

    # last_read_message: Optional["Message"] = Relationship(
    #     sa_relationship_kwargs={"foreign_keys": "[ChatMember.last_read_message_id]"},
    # )
    account: "Account" = Relationship(back_populates="chats")
    messages: list["Message"] = Relationship(
        back_populates="sender",
        passive_deletes="all",
        sa_relationship_kwargs={"foreign_keys": "[Message.sender_id]"},
    )
    chat_invites: list["ChatInvite"] = Relationship(
        back_populates="invited_by", passive_deletes="all"
    )

    # Unique constraint
    class Config:
        json_schema_extra = {
            "indexes": [
                {"fields": ["account_id", "chat_id"], "unique": True},
                {"fields": ["account_id", "status"]},
                {"fields": ["chat_id", "role"]},
            ]
        }


class MessageBase(AppSQLModel):
    message_type: MessageType = Field(default=MessageType.TEXT, index=True)
    content: Optional[str] = None  # Text content
    file_url: Optional[str] = Field(max_length=500, default=None)  # For files/images
    file_name: Optional[str] = Field(max_length=255, default=None)
    file_size: Optional[int] = None
    file_type: Optional[str] = Field(max_length=50, default=None)  # MIME type

    is_edited: bool = Field(default=False)
    edited_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )
    extra_data: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )  # Extra data


class Message(AppBaseModelMixin, MessageBase, table=True):
    __table_args__ = (Index("ix_chat_created_at", "chat_id", "created_at"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chat_id: uuid.UUID = Field(foreign_key="chat.id", index=True, ondelete="CASCADE")
    sender_id: Optional[uuid.UUID] = Field(
        foreign_key="chat_member.id", index=True, default=None, ondelete="SET NULL"
    )  # Null for system messages
    reply_to_id: Optional[uuid.UUID] = Field(
        foreign_key="message.id", default=None
    )  # For replies

    # Relationships
    chat: Chat = Relationship(back_populates="messages")
    sender: Optional["ChatMember"] = Relationship(
        back_populates="messages",
        sa_relationship_kwargs={"foreign_keys": "[Message.sender_id]"},
    )
    reply_to: Optional["Message"] = Relationship(
        back_populates="replies",
        sa_relationship_kwargs={
            "remote_side": "[Message.id]",
            "foreign_keys": "[Message.reply_to_id]",
        },
    )
    replies: list["Message"] = Relationship(
        back_populates="reply_to",
        sa_relationship_kwargs={
            "foreign_keys": "[Message.reply_to_id]",
            "overlaps": "reply_to",
        },
    )
    reactions: list["MessageReaction"] = Relationship(
        back_populates="message", cascade_delete=True
    )

    # Indexes
    class Config:
        json_schema_extra = {
            "indexes": [
                {"fields": ["chat_id", "created_at"]},
                {"fields": ["sender_id"]},
                {"fields": ["message_type"]},
                # {"fields": ["reply_to_id"]},
                # {"fields": ["is_deleted"]},
            ]
        }


class MessageReactionBase(AppSQLModel):
    emoji: str = Field(max_length=10)  # Emoji unicode or shortcode


class MessageReaction(AppBaseModelMixin, MessageReactionBase, table=True):
    __tablename__: str = "message_reaction"

    __table_args__ = (
        UniqueConstraint("account_id", "message_id", name="uix_account_message"),
        Index("ix_message_emoji", "message_id", "emoji"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    message_id: uuid.UUID = Field(foreign_key="message.id", index=True)
    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )

    # Relationships
    message: Message = Relationship(back_populates="reactions")
    account: "Account" = Relationship(back_populates="chat_reactions")

    # Unique constraint - one reaction per user per message per emoji
    class Config:
        json_schema_extra = {
            "indexes": [
                {"fields": ["account_id", "message_id"], "unique": True},
                {"fields": ["message_id", "emoji"]},
            ]
        }


class ChatInviteBase(AppSQLModel):
    invite_code: Optional[str] = Field(
        max_length=50, unique=True, index=True, default=None
    )  # Public invite link
    max_uses: Optional[int] = Field(default=None, ge=1)  # Limit uses for invite code
    current_uses: int = Field(default=0, ge=0)
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )
    is_active: bool = Field(default=True)


class ChatInvite(AppBaseModelMixin, ChatInviteBase, table=True):
    __tablename__: str = "chat_invite"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chat_id: uuid.UUID = Field(foreign_key="chat.id", index=True)
    invited_by_id: uuid.UUID = Field(foreign_key="chat_member.id", ondelete="CASCADE")
    invited_account_id: Optional[uuid.UUID] = Field(
        foreign_key="account.id", default=None, ondelete="CASCADE"
    )  # Specific user invite

    # Relationships
    chat: Chat = Relationship()
    invited_by: ChatMember = Relationship(back_populates="chat_invites")
    invited_account: "Account" = Relationship(back_populates="chat_invites")

    # Indexes
    class Config:
        json_schema_extra = {
            "indexes": [
                {"fields": ["chat_id", "is_active"]},
                # {"fields": ["invited_account_id"]},
                {"fields": ["invite_code"]},
                # {"fields": ["expires_at"]},
            ]
        }


# class ChatRead(AppSQLModel):
#     id: int
#     chat_type: ChatType
#     name: Optional[str]
#     description: Optional[str]
#     avatar_url: Optional[str]
#     privacy: Optional[GroupChatPrivacy]
#     is_active: bool
#     created_by: Optional[int]
#     course_id: Optional[int]
#     max_members: Optional[int]
#     created_at: datetime
#     updated_at: datetime


# class ChatWithMembers(ChatRead):
#     members: list["ChatMemberRead"] = []
#     member_count: int = 0
#     unread_count: Optional[int] = None  # For the requesting user


# class ChatMemberRead(AppSQLModel):
#     id: int
#     account_id: int
#     role: MemberRole
#     status: MemberStatus
#     joined_at: datetime
#     left_at: Optional[datetime]
#     notifications_enabled: bool
#     is_pinned: bool


# class MessageRead(AppSQLModel):
#     id: int
#     chat_id: int
#     sender_id: Optional[int]
#     message_type: MessageType
#     content: Optional[str]
#     file_url: Optional[str]
#     file_name: Optional[str]
#     file_size: Optional[int]
#     file_type: Optional[str]
#     reply_to_id: Optional[int]
#     is_edited: bool
#     edited_at: Optional[datetime]
#     is_deleted: bool
#     created_at: datetime


# class MessageWithReactions(MessageRead):
#     reactions: list["MessageReactionRead"] = []
#     reply_to: Optional["MessageRead"] = None


# class MessageReactionRead(AppSQLModel):
#     id: int
#     account_id: int
#     emoji: str
#     created_at: datetime


# class ChatInviteRead(AppSQLModel):
#     id: int
#     chat_id: int
#     invited_by: int
#     invited_account_id: Optional[int]
#     invite_code: Optional[str]
#     max_uses: Optional[int]
#     current_uses: int
#     expires_at: Optional[datetime]
#     is_active: bool
#     created_at: datetime


# # Chat API Models (Create/Update)
# class DirectChatCreate(AppSQLModel):
#     participant_account_id: int  # The other user in the direct chat


# class GroupChatCreate(AppSQLModel):
#     name: str = Field(min_length=1, max_length=255)
#     description: Optional[str] = None
#     privacy: GroupChatPrivacy = GroupChatPrivacy.PRIVATE
#     course_id: Optional[int] = None
#     max_members: Optional[int] = Field(default=100, ge=2, le=1000)
#     avatar_url: Optional[str] = None


# class GroupChatUpdate(AppSQLModel):
#     name: Optional[str] = Field(default=None, min_length=1, max_length=255)
#     description: Optional[str] = None
#     privacy: Optional[GroupChatPrivacy] = None
#     max_members: Optional[int] = Field(default=None, ge=2, le=1000)
#     avatar_url: Optional[str] = None


# class MessageCreate(AppSQLModel):
#     content: Optional[str] = None
#     message_type: MessageType = MessageType.TEXT
#     file_url: Optional[str] = None
#     file_name: Optional[str] = None
#     file_size: Optional[int] = None
#     file_type: Optional[str] = None
#     reply_to_id: Optional[int] = None


# class MessageUpdate(AppSQLModel):
#     content: Optional[str] = None


# class ChatMemberUpdate(AppSQLModel):
#     role: Optional[MemberRole] = None
#     notifications_enabled: Optional[bool] = None
#     is_pinned: Optional[bool] = None


# class ChatInviteCreate(AppSQLModel):
#     invited_account_id: Optional[int] = None  # For specific user invites
#     max_uses: Optional[int] = Field(default=None, ge=1, le=1000)
#     expires_at: Optional[datetime] = None


# class MessageReactionCreate(AppSQLModel):
#     emoji: str = Field(min_length=1, max_length=10)


# # Specialized response models
# class ChatlistResponse(AppSQLModel):
#     chats: list[ChatWithMembers]
#     total: int
#     has_more: bool


# class MessagelistResponse(AppSQLModel):
#     messages: list[MessageWithReactions]
#     total: int
#     has_more: bool
#     oldest_message_id: Optional[int] = None
#     newest_message_id: Optional[int] = None


# class ChatMemberlistResponse(AppSQLModel):
#     members: list[ChatMemberRead]
#     total: int
#     admins_count: int
#     active_members_count: int
