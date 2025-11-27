import base64
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Index, UniqueConstraint
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
from app.models.base import AppBaseModelMixin, AppSQLModel

if TYPE_CHECKING:
    from .annotation_model import DocumentAnnotation, DocumentChat
    from .chat_model import Chat
    from .comments_model import Comment, Rating
    from .user_model import Account


# Core Models
class CourseTag(AppBaseModelMixin, SQLModel, table=True):
    __tablename__: str = "course_tags"

    course_id: str = Field(foreign_key="course.id", primary_key=True)
    tag_id: uuid.UUID = Field(foreign_key="tag.id", primary_key=True)

    __table_args__ = (Index("idx_course_tags_lookup", "course_id", "tag_id"),)


class CourseBase(AppSQLModel):
    title: str = Field(
        max_length=255, min_length=3, index=True, description="add course title"
    )
    image: Optional[str] = None
    description: Optional[str] = Field(
        default=None, description="course description in full (markdown support)"
    )
    short_description: Optional[str] = Field(
        default=None, description="a short description", max_length=225
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


class Course(AppBaseModelMixin, CourseBase, table=True):
    __table_args__ = (
        Index("ix_search_filter", "title", "status", "visibility", "enrollment_type"),
    )

    id: str = Field(
        default_factory=lambda: base64.urlsafe_b64encode(
            str(uuid.uuid4()).encode()
        ).decode()[:7],
        primary_key=True,
    )
    account_id: Optional[uuid.UUID] = Field(
        foreign_key="account.id", ondelete="SET NULL"
    )
    slug: str = Field(unique=True, index=True)
    average_rating: float = Field(default=0.00)
    total_rating: int = Field(default=0)
    stars: int = Field(default=0)
    enrollment_count: int = Field(default=0)
    comment_count: int = Field(default=0)

    author: Optional["Account"] = Relationship(
        back_populates="courses",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    sections: list["Section"] = Relationship(
        back_populates="course",
        passive_deletes="all",
        sa_relationship_kwargs={
            "order_by": "Section.order_index",
        },
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
    tags: list["Tag"] = Relationship(
        back_populates="courses",
        link_model=CourseTag,
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class TagBase(AppSQLModel):
    name: str = Field(
        max_length=50,
        index=True,
        description="Tag name (e.g., 'python', 'machine-learning')",
    )
    usage_count: int = Field(
        default=0, index=True, description="Number of times this tag is used"
    )


class Tag(AppBaseModelMixin, TagBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    courses: list["Course"] = Relationship(back_populates="tags", link_model=CourseTag)


class SectionBase(AppSQLModel):
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


class Section(AppBaseModelMixin, SectionBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    course_id: str = Field(foreign_key="course.id", index=True, ondelete="CASCADE")

    # Relationships
    course: Course = Relationship(back_populates="sections")
    modules: list["Module"] = Relationship(
        back_populates="section",
        passive_deletes="all",
        sa_relationship_kwargs={
            "order_by": "Module.order_index",
        },
    )

    __table_args__ = (
        Index("ix_course_order", "course_id", "order_index"),
        UniqueConstraint("course_id", "order_index", name="uq_course_order"),
    )


class ModuleBase(AppSQLModel):
    title: str = Field(max_length=255)
    description: Optional[str] = None

    content_data: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    order_index: int = Field(index=True)
    estimated_duration_minutes: Optional[int] = None
    is_required: bool = Field(default=True)
    prerequisites: Optional[list[str]] = Field(default=None, sa_column=Column(JSONB))
    settings: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))


class Module(AppBaseModelMixin, ModuleBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    section_id: uuid.UUID = Field(
        foreign_key="section.id", index=True, ondelete="CASCADE"
    )

    section: Section = Relationship(back_populates="modules")
    video_content: Optional["VideoContent"] = Relationship(
        back_populates="module",
        sa_relationship_kwargs={
            "uselist": False,
            "cascade": "all, delete-orphan",
        },
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
    module_type: ModuleType = Field(index=True)

    # 💡 Composite index for ordering
    __table_args__ = (
        Index("ix_section_order", "section_id", "order_index"),
        UniqueConstraint("section_id", "order_index", name="uq_section_order"),
    )


class ModuleAttachmentBase(AppSQLModel):
    attachment_type: AttachmentType
    file_url: str = Field(max_length=500)
    external_file_id: Optional[str] = Field(max_length=255, default=None, index=True)
    embed_url: Optional[str] = Field(max_length=500, default=None)
    title: Optional[str] = None
    description: Optional[str] = None
    document_type: Optional[DocumentPlatform] = Field(default=None)
    file_type: Optional[str] = Field(max_length=50, default=None)


class ModuleAttachment(AppBaseModelMixin, ModuleAttachmentBase, table=True):
    __tablename__: str = "module_attachment"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: uuid.UUID = Field(
        foreign_key="module.id", index=True, ondelete="CASCADE"
    )
    module: Module = Relationship(back_populates="attachments")


class VideoContentBase(AppSQLModel):
    platform: VideoPlatform
    external_video_id: str = Field(max_length=255, index=True)
    video_url: str = Field(max_length=500)
    embed_url: Optional[str] = Field(max_length=500, default=None)
    thumbnail_url: Optional[str] = Field(max_length=500, default=None)
    duration_seconds: Optional[int] = None
    title: Optional[str] = Field(max_length=255, default=None)
    description: Optional[str] = None
    embed_settings: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )


# Content-specific models
class VideoContent(AppBaseModelMixin, VideoContentBase, table=True):
    __tablename__: str = "video_content"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: uuid.UUID = Field(
        foreign_key="module.id", unique=True, ondelete="CASCADE"
    )

    # Relationships
    module: Module = Relationship(back_populates="video_content")


class DocumentBase(AppSQLModel):
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


class DocumentContent(AppBaseModelMixin, DocumentBase, table=True):
    __tablename__: str = "document_content"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: uuid.UUID = Field(
        foreign_key="module.id", unique=True, ondelete="CASCADE"
    )

    # Relationships
    module: Module = Relationship(back_populates="document_content")
    annotations: list["DocumentAnnotation"] = Relationship(
        back_populates="document", passive_deletes="all"
    )

    chats: list["DocumentChat"] = Relationship(
        back_populates="document", passive_deletes="all"
    )


class QuizContentBase(AppSQLModel):
    quiz_settings: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    passing_score: Optional[float] = Field(default=None, ge=0, le=100)
    show_results: ShowResults = Field(default=ShowResults.IMMEDIATE)
    randomize_questions: bool = Field(default=False)


class QuizContent(AppBaseModelMixin, QuizContentBase, table=True):
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


class QuizQuestionBase(AppSQLModel):
    question_text: str
    question_type: QuestionType
    options: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    correct_answer: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    points: float = Field(default=1.0, ge=0)
    explanation: Optional[str] = None
    order_index: Optional[int] = None


class QuizQuestion(AppBaseModelMixin, QuizQuestionBase, table=True):
    __tablename__: str = "quiz_question"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(
        foreign_key="quiz_content.id", index=True, ondelete="CASCADE"
    )

    # Relationships
    quiz: QuizContent = Relationship(back_populates="questions")


class CourseEnrollmentBase(AppSQLModel):
    status: EnrollmentStatus = Field(default=EnrollmentStatus.ACTIVE, index=True)


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
    course_id: Optional[str] = Field(
        foreign_key="course.id", index=True, ondelete="SET NULL"
    )
    enrollment_date: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completion_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )
    progress_percentage: float = Field(default=0.0, ge=0, le=100)
    last_accessed: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    course: Optional[Course] = Relationship(back_populates="enrollments")
    account: "Account" = Relationship(back_populates="enrollments")

    # Unique constraint
    class Config:
        json_schema_extra = {
            "indexes": [{"fields": ["account_id", "course_id"], "unique": True}]
        }


class CourseProgressBase(AppSQLModel):
    status: ModuleProgressStatus = Field(
        default=ModuleProgressStatus.NOT_STARTED, index=True
    )
    start_time: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )
    completion_time: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )
    time_spent_seconds: int = Field(default=0, ge=0)
    progress_data: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    next_module: Optional[str] = Field(default=None)
    next_section: Optional[str] = Field(default=None)

    current_streak: int = Field(default=0)
    longest_streak: int = Field(default=0)
    last_active_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )


class CourseProgress(AppBaseModelMixin, CourseProgressBase, table=True):
    __tablename__: str = "course_progress"

    __table_args__ = (
        UniqueConstraint("account_id", "course_id", name="ix_progress_account_course"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(
        foreign_key="account.id", index=True, ondelete="CASCADE"
    )
    course_id: Optional[str] = Field(
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


class QuizAttemptBase(AppSQLModel):
    attempt_number: int = Field(ge=1)
    start_time: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    completion_time: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        ),
    )
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
