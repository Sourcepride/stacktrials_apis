import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.common.enum import UserRole
from app.models.base import AppBaseModelMixin, AppSQLModel

if TYPE_CHECKING:
    from .annotation_model import DocumentAnnotation, DocumentChat
    from .chat_model import Chat, ChatInvite, ChatMember, Message, MessageReaction
    from .comments_model import Comment, CommentLike, Rating
    from .courses_model import Course, CourseEnrollment, CourseProgress, QuizAttempt
    from .notification_model import Notification
    from .provider_model import Provider


class AccountBase(AppSQLModel):
    email: str = Field(index=True, unique=True)
    username: Optional[str] = Field(
        index=True, unique=True, nullable=True, default=None
    )
    is_active: bool = Field(default=True)
    is_super_user: bool = Field(default=False)
    role: UserRole = Field(default=UserRole.USER)


class Account(AppBaseModelMixin, AccountBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    profile: Optional["Profile"] = Relationship(
        back_populates="account",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )
    providers: list["Provider"] = Relationship(
        back_populates="account",
        passive_deletes="all",
        # sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    courses: list["Course"] = Relationship(
        back_populates="author",
    )
    quizes: list["QuizAttempt"] = Relationship(
        back_populates="account", passive_deletes="all"
    )
    enrollments: list["CourseEnrollment"] = Relationship(
        back_populates="account", passive_deletes="all"
    )
    progress_records: list["CourseProgress"] = Relationship(
        back_populates="account", passive_deletes="all"
    )
    created_chats: list["Chat"] = Relationship(
        back_populates="account", passive_deletes="all"
    )
    chats: list["ChatMember"] = Relationship(
        back_populates="account", passive_deletes="all"
    )
    chat_reactions: list["MessageReaction"] = Relationship(
        back_populates="account", passive_deletes="all"
    )
    chat_invites: list["ChatInvite"] = Relationship(
        back_populates="invited_account", passive_deletes="all"
    )
    ratings: list["Rating"] = Relationship(
        back_populates="account", passive_deletes="all"
    )
    comments: list["Comment"] = Relationship(
        back_populates="account",
        sa_relationship_kwargs={"foreign_keys": "[Comment.creator_id]"},
        passive_deletes="all",
    )
    mentions: list["Comment"] = Relationship(
        back_populates="mention",
        sa_relationship_kwargs={"foreign_keys": "[Comment.mention_id]"},
        passive_deletes="all",
    )
    comment_likes: list["CommentLike"] = Relationship(
        back_populates="account",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    document_annotations: list["DocumentAnnotation"] = Relationship(
        back_populates="account", passive_deletes="all"
    )

    document_chats: list["DocumentChat"] = Relationship(
        back_populates="account", passive_deletes="all"
    )
    notifications: list["Notification"] = Relationship(
        back_populates="account", passive_deletes="all"
    )


class ProfileBase(AppSQLModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    x: Optional[str] = None
    youtube: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    language: Optional[str] = None


class Profile(AppBaseModelMixin, ProfileBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, unique=True, ondelete="CASCADE"
    )
    account: Account = Relationship(back_populates="profile")
