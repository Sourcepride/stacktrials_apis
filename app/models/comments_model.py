# ratings

# comments

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import AppBaseModelMixin

if TYPE_CHECKING:
    from .courses_model import Course
    from .user_model import Account


class RatingBase(SQLModel):
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


class CommentBase(SQLModel):
    message: str
    likes: int = Field(default=0)
    comment_count: int = Field(default=0)
    is_rating: bool = Field(default=False)


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
        sa_relationship_kwargs={"remote_side": "Comment.id"}
    )
    replies: list["Comment"] = Relationship(
        sa_relationship_kwargs={"remote_side": "Comment.reply_to_id"}
    )

    rating: Optional["Rating"] = Relationship(
        back_populates="comment",
        sa_relationship_kwargs={
            "uselist": False,
            "cascade": "all, delete-orphan",
            "single_parent": True,
        },
    )
