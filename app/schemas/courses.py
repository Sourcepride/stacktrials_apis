import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.common.enum import ModuleType, ProgressionType
from app.models.comments_model import CommentBase, RatingBase
from app.models.courses_model import (
    CourseBase,
    CourseEnrollmentBase,
    CourseProgressBase,
    DocumentBase,
    ModuleAttachmentBase,
    ModuleBase,
    QuizContent,
    QuizContentBase,
    QuizQuestionBase,
    SectionBase,
    VideoContentBase,
)
from app.models.user_model import Account, AccountBase, Profile
from app.schemas.base import PaginatedSchema


class AccountRead(AccountBase):
    id: uuid.UUID
    profile: Optional["Profile"] = None


class CourseRead(CourseBase):
    id: str
    slug: str
    account_id: Optional[uuid.UUID] = None
    author: Optional["AccountRead"] = None
    average_rating: float
    total_rating: int
    stars: int
    enrollment_count: int
    comment_count: int
    updated_at: datetime


class PaginatedCourse(PaginatedSchema):
    items: list[CourseRead]


class CourseCreate(CourseBase):
    tags: list[str] = []


class CourseUpdate(CourseBase):
    pass


class SectionRead(SectionBase):
    id: uuid.UUID
    course_id: str


class SectionCreate(SectionBase):
    course_id: str


class SectionUpdate(SectionBase):
    title: Optional[str] = None
    order_index: Optional[int] = None
    is_optional: Optional[bool] = None
    progression_type: Optional[ProgressionType] = None


class VideoContentRead(VideoContentBase):
    id: uuid.UUID
    module_id: uuid.UUID


class DocumentContentRead(DocumentBase):
    id: uuid.UUID
    module_id: uuid.UUID


class QuizContentRead(QuizContentBase):
    id: uuid.UUID
    module_id: uuid.UUID
    questions: list["QuizQuestionRead"]


class QuizQuestionRead(QuizQuestionBase):
    id: uuid.UUID
    quiz_id: uuid.UUID


class ModuleAttachmentRead(ModuleAttachmentBase):
    id: uuid.UUID
    module_id: uuid.UUID


class ModuleReadMin(ModuleBase):
    id: uuid.UUID
    section_id: uuid.UUID
    module_type: ModuleType


class ModuleRead(ModuleBase):
    id: uuid.UUID
    section_id: uuid.UUID
    video_content: Optional["VideoContentRead"] = None
    document_content: Optional["DocumentContentRead"] = None
    quiz_content: Optional["QuizContent"] = None
    attachments: list["ModuleAttachmentRead"]
    module_type: ModuleType


class ModuleCreate(ModuleBase):
    section_id: uuid.UUID
    module_type: ModuleType


class ModuleUpdate(ModuleBase):
    title: Optional[str] = None
    order_index: Optional[int] = None
    is_required: Optional[bool] = None


class VideoContentCreate(VideoContentBase):
    module_id: uuid.UUID


class VideoContentUpdate(VideoContentBase):
    pass


class DocumentContentCreate(DocumentBase):

    module_id: uuid.UUID


class DocumentContentUpdate(DocumentBase):
    pass


class QuizContentCreate(QuizContentBase):
    module_id: uuid.UUID
    questions: list["QuizQuestionRead"]


class QuizQuestionCreate(QuizQuestionBase):
    quiz_id: uuid.UUID


class ModuleAttachmentCreate(ModuleAttachmentBase):
    module_id: uuid.UUID


class CourseProgressRead(CourseProgressBase):
    id: uuid.UUID
    account_id: uuid.UUID
    course_id: str


class CoureProgressCreate(CourseProgressBase):
    account_id: uuid.UUID
    course_id: str


class CourseEnrollmentRead(CourseEnrollmentBase):
    id: uuid.UUID
    account_id: uuid.UUID
    course_id: str


class CourseEnrollmentCreate(CourseEnrollmentBase):
    account_id: uuid.UUID
    course_id: str


class CourseRatingRead(RatingBase):
    id: uuid.UUID
    account_id: uuid.UUID
    course_id: str
    comment_id: Optional[uuid.UUID]
    comment: Optional["CourseCommentRead"] = None
    created_at: datetime


class PaginatedRatings(PaginatedSchema):
    items: list[CourseRatingRead]


class CourseRatingCreate(RatingBase):
    course_id: str


class CourseCommentRead(CommentBase):
    id: uuid.UUID
    account: "AccountRead"
    creator_id: uuid.UUID
    course_id: str
    reply_to_id: Optional[uuid.UUID]
    mention_id: Optional[uuid.UUID]
    reply_to: Optional[CommentBase] = None
    mention: Optional[AccountRead] = None
    created_at: datetime
    likes: int
    comment_count: int
    is_rating: bool
    is_liked: Optional[bool] = False


class PaginatedComments(PaginatedSchema):
    items: list[CourseCommentRead]


class CourseCommentCreate(CommentBase):
    course_id: str
    reply_to_id: Optional[uuid.UUID] = None


class CourseCommentUpdate(CommentBase):
    pass


class CreateAttacment(BaseModel):
    data: list[ModuleAttachmentCreate]


class SectionContentReadMin(SectionRead):
    modules: list[ModuleReadMin]


class CourseContentReadMin(CourseRead):
    sections: list[SectionContentReadMin]


class SectionContentReadFull(SectionRead):
    modules: list[ModuleRead]


class CourseContentReadFull(CourseContentReadMin):
    sections: list[SectionContentReadFull]
