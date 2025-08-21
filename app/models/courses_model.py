import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

from app.common.enum import (
    AttachmentType,
    CourseStatus,
    DifficultyLevel,
    DocumentPlatform,
    EnrollmentStatus,
    EnrollmentType,
    ModuleProgressStatus,
    ModuleType,
    ProgressionType,
    QuestionType,
    QuizAttemptStatus,
    ShowResults,
    VideoPlatform,
    VisibilityType,
)
from app.models.base import AppBaseModel

if TYPE_CHECKING:
    from .chat_model import Chat
    from .comments_model import Comment, Rating
    from .user_model import Account


# Core Models


class CourseBase(AppBaseModel):
    title: str = Field(max_length=255, index=True, description="add course title")
    slug: str = Field(unique=True, index=True)
    description: Optional[str] = Field(
        default=None, description="course description in full (markdown support)"
    )
    short_description: Optional[str] = Field(
        default=None, description="a short description"
    )
    learning_objectives: Optional[list[str]] = Field(
        default=None,
        sa_column=Column(JSONB),
        description="course learning object (optional)",
    )
    prerequisites: Optional[list[str]] = Field(default=None, sa_column=Column(JSONB))
    difficulty_level: DifficultyLevel = Field(
        default=DifficultyLevel.BEGINNER, index=True
    )
    estimated_duration_hours: Optional[int] = None
    language: str = Field(default="en", max_length=10)
    status: CourseStatus = Field(default=CourseStatus.DRAFT, index=True)
    enrollment_type: EnrollmentType = Field(default=EnrollmentType.OPEN)
    visibility: VisibilityType = Field(default=VisibilityType.PUBLIC)
    certification_enabled: bool = Field(default=False)
    average_rating: float = Field(default=0.00)
    total_rating: int = Field(default=0)
    stars: int = Field(default=0)


class Course(CourseBase, table=True):
    __table_args__ = (
        Index("ix_search_filter", "title", "status", "visibility", "enrollment_type"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # Relationships
    account_id: Optional[uuid.UUID] = Field(
        foreign_key="account.id", ondelete="SET NULL"
    )
    author: Optional["Account"] = Relationship(back_populates="courses")
    sections: list["Section"] = Relationship(
        back_populates="course", passive_deletes="all"
    )
    enrollments: list["CourseEnrollment"] = Relationship(
        back_populates="course", passive_deletes="all"
    )
    progress_records: list["CourseProgress"] = Relationship(
        back_populates="course", passive_deletes="all"
    )
    chats: list["Chat"] = Relationship(back_populates="course", passive_deletes="all")
    ratings: list["Rating"] = Relationship(
        back_populates="course", passive_deletes="all"
    )
    comments: list["Comment"] = Relationship(
        back_populates="course", passive_deletes="all"
    )


class SectionBase(AppBaseModel):
    title: str = Field(max_length=255)
    description: Optional[str] = None
    learning_objectives: Optional[list[str]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    order_index: int = Field(index=True)
    estimated_duration_minutes: Optional[int] = None
    is_optional: bool = Field(default=False)
    progression_type: ProgressionType = Field(default=ProgressionType.SEQUENTIAL)
    completion_criteria: Optional[list[str]] = Field(
        default=None, sa_column=Column(JSONB)
    )


class Section(SectionBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    course_id: uuid.UUID = Field(
        foreign_key="course.id", index=True, ondelete="CASCADE"
    )

    # Relationships
    course: Course = Relationship(back_populates="sections")
    modules: list["Module"] = Relationship(
        back_populates="section", passive_deletes="all"
    )

    __table_args__ = (
        Index("ix_course_order", "course_id", "order_index"),
        UniqueConstraint("course_id", "order_index", name="uq_course_order"),
    )


class ModuleBase(AppBaseModel):
    title: str = Field(max_length=255)
    description: Optional[str] = None
    module_type: ModuleType = Field(index=True)
    content_data: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    order_index: int = Field(index=True)
    estimated_duration_minutes: Optional[int] = None
    is_required: bool = Field(default=True)
    prerequisites: Optional[list[str]] = Field(default=None, sa_column=Column(JSONB))
    settings: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))


class Module(ModuleBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    section_id: uuid.UUID = Field(
        foreign_key="section.id", index=True, ondelete="CASCADE"
    )

    section: Section = Relationship(back_populates="modules")
    video_content: Optional["VideoContent"] = Relationship(
        back_populates="module",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )
    document_content: Optional["DocumentContent"] = Relationship(
        back_populates="module",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )
    quiz_content: Optional["QuizContent"] = Relationship(
        back_populates="module",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )

    attachments: list["ModuleAttachment"] = Relationship(
        back_populates="module", passive_deletes="all"
    )

    # 💡 Composite index for ordering
    __table_args__ = (
        Index("ix_section_order", "section_id", "order_index"),
        UniqueConstraint("section_id", "order_index", name="uq_section_order"),
    )


class ModuleAttachmentBase(AppBaseModel):
    attachment_type: AttachmentType
    file_url: str = Field(max_length=500)
    external_file_id: Optional[str] = Field(max_length=255, default=None, index=True)
    embed_url: Optional[str] = Field(max_length=500, default=None)
    title: Optional[str] = None
    description: Optional[str] = None


class ModuleAttachment(ModuleAttachmentBase, table=True):
    __tablename__: str = "module_attachment"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: uuid.UUID = Field(
        foreign_key="module.id", index=True, ondelete="CASCADE"
    )
    module: Module = Relationship(back_populates="attachments")


class VideoContentBase(AppBaseModel):
    platform: VideoPlatform
    external_video_id: str = Field(max_length=255, index=True)
    video_url: str = Field(max_length=500)
    thumbnail_url: Optional[str] = Field(max_length=500, default=None)
    duration_seconds: Optional[int] = None
    title: Optional[str] = Field(max_length=255, default=None)
    description: Optional[str] = None
    embed_settings: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )


# Content-specific models
class VideoContent(VideoContentBase, table=True):
    __tablename__: str = "video_content"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: uuid.UUID = Field(
        foreign_key="module.id", unique=True, ondelete="CASCADE"
    )

    # Relationships
    module: Module = Relationship(back_populates="video_content")


class DocumentBase(AppBaseModel):
    platform: DocumentPlatform
    external_file_id: Optional[str] = Field(max_length=255, default=None, index=True)
    file_url: str = Field(max_length=500)
    embed_url: Optional[str] = Field(max_length=500, default=None)
    file_name: str = Field(max_length=255)
    file_type: str = Field(max_length=50)
    file_size_bytes: Optional[int] = None
    viewer_settings: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )


class DocumentContent(DocumentBase, table=True):
    __tablename__: str = "document_content"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: uuid.UUID = Field(
        foreign_key="module.id", unique=True, ondelete="CASCADE"
    )

    # Relationships
    module: Module = Relationship(back_populates="document_content")


class QuizContentBase(AppBaseModel):
    quiz_settings: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    passing_score: Optional[float] = Field(default=None, ge=0, le=100)
    show_results: ShowResults = Field(default=ShowResults.IMMEDIATE)
    randomize_questions: bool = Field(default=False)


class QuizContent(QuizContentBase, table=True):
    __tablename__: str = "quiz_content"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: uuid.UUID = Field(
        foreign_key="module.id", unique=True, ondelete="CASCADE"
    )

    # Relationships
    module: Module = Relationship(back_populates="quiz_content")
    questions: list["QuizQuestion"] = Relationship(
        back_populates="quiz", passive_deletes="all"
    )
    attempts: list["QuizAttempt"] = Relationship(
        back_populates="quiz", passive_deletes="all"
    )


class QuizQuestionBase(AppBaseModel):
    question_text: str
    question_type: QuestionType
    options: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    correct_answer: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    points: float = Field(default=1.0, ge=0)
    explanation: Optional[str] = None
    order_index: Optional[int] = None


class QuizQuestion(QuizQuestionBase, table=True):
    __tablename__: str = "quiz_question"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(
        foreign_key="quiz_content.id", index=True, ondelete="CASCADE"
    )

    # Relationships
    quiz: QuizContent = Relationship(back_populates="questions")


class CourseEnrollmentBase(SQLModel):
    enrollment_date: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    completion_date: Optional[datetime] = None
    status: EnrollmentStatus = Field(default=EnrollmentStatus.ACTIVE, index=True)
    progress_percentage: float = Field(default=0.0, ge=0, le=100)
    last_accessed: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


# Progress tracking models
class CourseEnrollment(CourseEnrollmentBase, table=True):
    __tablename__: str = "course_enrollment"

    __table_args__ = (
        UniqueConstraint("account_id", "course_id", name="ix_enroll_account_course"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    course_id: Optional[uuid.UUID] = Field(
        foreign_key="course.id", index=True, ondelete="SET NULL"
    )

    # Relationships
    course: Optional[Course] = Relationship(back_populates="enrollments")
    account: "Account" = Relationship(back_populates="enrollments")

    # Unique constraint
    class Config:
        json_schema_extra = {
            "indexes": [{"fields": ["account_id", "course_id"], "unique": True}]
        }


class CourseProgressBase(AppBaseModel):
    status: ModuleProgressStatus = Field(
        default=ModuleProgressStatus.NOT_STARTED, index=True
    )
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    time_spent_seconds: int = Field(default=0, ge=0)
    progress_data: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )

    current_streak: int = Field(default=0)
    longest_streak: int = Field(default=0)
    last_active_date: Optional[datetime] = None


class CourseProgress(CourseProgressBase, table=True):
    __tablename__: str = "course_progress"

    __table_args__ = (
        UniqueConstraint("account_id", "course_id", name="ix_progress_account_course"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    course_id: Optional[uuid.UUID] = Field(
        foreign_key="course.id", index=True, ondelete="SET NULL"
    )

    # Relationships
    course: Optional[Course] = Relationship(back_populates="progress_records")
    account: "Account" = Relationship(back_populates="progress_records")

    # Unique constraint
    class Config:
        json_schema_extra = {
            "indexes": [{"fields": ["account_id", "course_id"], "unique": True}]
        }


class QuizAttemptBase(SQLModel):
    attempt_number: int = Field(ge=1)
    start_time: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    completion_time: Optional[datetime] = None
    score: Optional[float] = Field(default=None, ge=0, le=100)
    answers: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    status: QuizAttemptStatus = Field(default=QuizAttemptStatus.IN_PROGRESS)


class QuizAttempt(QuizAttemptBase, table=True):
    __tablename__: str = "quiz_attempt"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    quiz_id: Optional[uuid.UUID] = Field(
        foreign_key="quiz_content.id", index=True, ondelete="SET NULL"
    )

    # Relationships
    quiz: Optional[QuizContent] = Relationship(back_populates="attempts")
    account: "Account" = Relationship(back_populates="quizes")


# save
