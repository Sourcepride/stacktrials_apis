import uuid
from ast import List
from typing import Optional

from app.models.comments_model import CommentBase, Rating, RatingBase
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
from app.models.user_model import Account
from app.schemas.base import PaginatedSchema


class CourseRead(CourseBase):
    id: str
    slug: str
    account_id: Optional[uuid.UUID] = None
    author: Optional["Account"] = None
    average_rating: float
    total_rating: int
    stars: int
    enrollment_count: int
    comment_count: int


class PaginatedCourse(PaginatedSchema):
    items: list[CourseRead]


class CourseCreate(CourseBase):
    tags: list[str] = []


class SectionRead(SectionBase):
    id: uuid.UUID
    course_id: str


class SectionCreate(SectionBase):
    course_id: str


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


class ModuleRead(ModuleBase):
    id: uuid.UUID
    section_id: uuid.UUID
    video_content: Optional["VideoContentRead"]
    document_content: Optional["DocumentContentRead"] = None
    quiz_content: Optional["QuizContent"] = None
    attachments: list["ModuleAttachmentRead"]


class ModuleCreate(ModuleBase):
    section_id: uuid.UUID


class VideoContentCreate(VideoContentBase):
    module_id: uuid.UUID


class DocumentContentCreate(DocumentBase):

    module_id: uuid.UUID


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
    comment_id: str


class CourseRatingCreate(RatingBase):
    course_id: str
    comment_id: str


class CourseCommentRead(CommentBase):
    id: uuid.UUID
    creator_id: uuid.UUID
    course_id: str
    reply_to_id: uuid.UUID
    mention_id: uuid.UUID
    reply_to: Optional[CommentBase] = None
    mention: Optional[Account] = None


class CourseCommentCreate(CommentBase):
    creator_id: uuid.UUID
    course_id: str
    reply_to_id: Optional[uuid.UUID] = None
