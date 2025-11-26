# ratings

# comments

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship

from app.models.base import AppBaseModelMixin, AppSQLModel

if TYPE_CHECKING:
    from .courses_model import Course
    from .user_model import Account


class RatingBase(AppSQLModel):
    star: int = Field(le=5, ge=1)
    message: str


class Rating(AppBaseModelMixin, RatingBase, table=True):
    __table_args__ = (
        UniqueConstraint("account_id", "course_id", name="uix_account_course"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    course_id: Optional[str] = Field(
        foreign_key="course.id", index=True, default=None, ondelete="SET NULL"
    )
    comment_id: Optional[uuid.UUID] = Field(
        foreign_key="comment.id", ondelete="CASCADE", default=None
    )

    course: Optional["Course"] = Relationship(back_populates="ratings")
    account: "Account" = Relationship(back_populates="ratings")
    comment: Optional["Comment"] = Relationship(back_populates="rating")

    # unique constraint
    class Config:
        json_schema_extra = {
            "indexes": [
                {"fields": ["account_id", "course_id"], "unique": True},
                {"fields": ["course_id"]},
                {"fields": ["account_id"]},
            ]
        }


class CommentBase(AppSQLModel):
    message: str


class Comment(AppBaseModelMixin, CommentBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    creator_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    course_id: str = Field(foreign_key="course.id", index=True, ondelete="CASCADE")
    reply_to_id: Optional[uuid.UUID] = Field(
        foreign_key="comment.id", default=None
    )  # For replies

    mention_id: Optional[uuid.UUID] = Field(
        foreign_key="account.id", default=None, index=True, ondelete="CASCADE"
    )
    likes: int = Field(default=0)
    comment_count: int = Field(default=0)
    is_rating: bool = Field(default=False)

    account: "Account" = Relationship(
        back_populates="comments",
        sa_relationship_kwargs={"foreign_keys": "[Comment.creator_id]"},
    )
    mention: Optional["Account"] = Relationship(
        back_populates="mentions",
        sa_relationship_kwargs={"foreign_keys": "[Comment.mention_id]"},
    )
    course: "Course" = Relationship(back_populates="comments")

    reply_to: Optional["Comment"] = Relationship(
        back_populates="replies",
        sa_relationship_kwargs={
            "remote_side": "Comment.id",
        },
    )

    replies: list["Comment"] = Relationship(
        back_populates="reply_to",
        sa_relationship_kwargs={
            "overlaps": "reply_to",
        },
    )

    rating: Optional["Rating"] = Relationship(
        back_populates="comment",
        sa_relationship_kwargs={
            "uselist": False,
            "cascade": "all, delete-orphan",
            "single_parent": True,
        },
    )

    comment_likes: list["CommentLike"] = Relationship(
        back_populates="comment",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class CommentLike(AppBaseModelMixin, table=True):

    __table_args__ = (
        UniqueConstraint("account_id", "comment_id", name="uix_account_comment"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    comment_id: uuid.UUID = Field(
        foreign_key="comment.id", index=True, ondelete="CASCADE"
    )

    account: "Account" = Relationship(back_populates="comment_likes")
    comment: "Comment" = Relationship(back_populates="comment_likes")
