import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

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
    QuizAttemptStatus,
    ShowResults,
    VideoPlatform,
    VisibilityType,
)
from app.models.base import AppBaseModel

if TYPE_CHECKING:
    from .user_model import Account


# Base model classes
class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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


class Course(CourseBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # Relationships
    account_id: uuid.UUID = Field(foreign_key="account.id", ondelete="SET NULL")
    author: Optional["Account"] = Relationship(back_populates="courses")
    sections: List["Section"] = Relationship(
        back_populates="course", passive_deletes="all"
    )
    enrollments: List["CourseEnrollment"] = Relationship(back_populates="course")


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
        foreign_key="courses.id", index=True, ondelete="CASCADE"
    )

    # Relationships
    course: Course = Relationship(back_populates="sections")
    modules: List["Module"] = Relationship(
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
        foreign_key="sections.id", index=True, ondelete="CASCADE"
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
    progress_records: List["ModuleProgress"] = Relationship(back_populates="module")
    attachments: List["ModuleAttachment"] = Relationship(
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
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: int = Field(foreign_key="modules.id", unique=True, ondelete="CASCADE")

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
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: int = Field(foreign_key="modules.id", unique=True, ondelete="CASCADE")

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
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: int = Field(foreign_key="modules.id", unique=True, ondelete="CASCADE")

    # Relationships
    module: Module = Relationship(back_populates="quiz_content")
    questions: List["QuizQuestion"] = Relationship(
        back_populates="quiz", cascade_delete=True
    )
    attempts: List["QuizAttempt"] = Relationship(
        back_populates="quiz", passive_deletes="all"
    )


class QuizQuestionBase(AppBaseModel):
    question_text: str
    question_type: QuestionType
    options: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    correct_answer: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    points: float = Field(default=1.0, ge=0)
    explanation: Optional[str] = None
    order_index: Optional[int] = None


class QuizQuestion(SQLModel, table=True):

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: int = Field(foreign_key="quiz_content.id", index=True)

    # Relationships
    quiz: QuizContent = Relationship(back_populates="questions")


# Progress tracking models
class CourseEnrollment(SQLModel, table=True):

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    enrollment_date: datetime = Field(default_factory=datetime.utcnow)
    completion_date: Optional[datetime] = None
    status: EnrollmentStatus = Field(default=EnrollmentStatus.ACTIVE, index=True)
    progress_percentage: float = Field(default=0.0, ge=0, le=100)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    course: Course = Relationship(back_populates="enrollments")

    # Unique constraint
    class Config:
        schema_extra = {
            "indexes": [{"fields": ["user_id", "course_id"], "unique": True}]
        }


class ModuleProgress(TimestampMixin, table=True):

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(index=True)
    module_id: int = Field(foreign_key="modules.id", index=True)
    status: ModuleProgressStatus = Field(
        default=ModuleProgressStatus.NOT_STARTED, index=True
    )
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    time_spent_seconds: int = Field(default=0, ge=0)
    progress_data: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )

    # Relationships
    module: Module = Relationship(back_populates="progress_records")

    # Unique constraint
    class Config:
        schema_extra = {
            "indexes": [{"fields": ["user_id", "module_id"], "unique": True}]
        }


class QuizAttemptBase(SQLModel):
    attempt_number: int = Field(ge=1)
    start_time: datetime = Field(default_factory=datetime.utcnow)
    completion_time: Optional[datetime] = None
    score: Optional[float] = Field(default=None, ge=0, le=100)
    answers: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    status: QuizAttemptStatus = Field(default=QuizAttemptStatus.IN_PROGRESS)


class QuizAttempt(QuizAttemptBase, table=True):

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="account.id", index=True, ondelete="CASCADE")
    quiz_id: int = Field(foreign_key="quiz_content.id", index=True, ondelete="SET NULL")

    # Relationships
    quiz: QuizContent = Relationship(back_populates="attempts")
    account: "Account" = Relationship(back_populates="quizes")


# Pydantic models for API responses (read models)
class CourseRead(SQLModel):
    id: int
    title: str
    slug: str
    description: Optional[str]
    short_description: Optional[str]
    difficulty_level: DifficultyLevel
    estimated_duration_hours: Optional[int]
    status: CourseStatus
    enrollment_type: EnrollmentType
    certification_enabled: bool
    created_at: datetime
    updated_at: datetime


class CourseWithSections(CourseRead):
    sections: List["SectionRead"] = []


class SectionRead(SQLModel):
    id: int
    title: str
    description: Optional[str]
    order_index: int
    estimated_duration_minutes: Optional[int]
    is_optional: bool
    progression_type: ProgressionType


class SectionWithModules(SectionRead):
    modules: List["ModuleRead"] = []


class ModuleRead(SQLModel):
    id: int
    title: str
    description: Optional[str]
    module_type: ModuleType
    order_index: int
    estimated_duration_minutes: Optional[int]
    is_required: bool


class VideoContentRead(SQLModel):
    id: int
    platform: VideoPlatform
    external_video_id: str
    video_url: str
    thumbnail_url: Optional[str]
    duration_seconds: Optional[int]
    title: Optional[str]
    embed_settings: Optional[Dict[str, Any]]


class DocumentContentRead(SQLModel):
    id: int
    platform: DocumentPlatform
    file_url: str
    embed_url: Optional[str]
    file_name: str
    file_type: str
    viewer_settings: Optional[Dict[str, Any]]


class ModuleProgressRead(SQLModel):
    id: int
    user_id: int
    module_id: int
    status: ModuleProgressStatus
    progress_percentage: float
    time_spent_seconds: int
    start_time: Optional[datetime]
    completion_time: Optional[datetime]


# Pydantic models for API requests (create/update models)
class CourseCreate(SQLModel):
    title: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    learning_objectives: Optional[Dict[str, Any]] = None
    prerequisites: Optional[Dict[str, Any]] = None
    difficulty_level: DifficultyLevel = DifficultyLevel.BEGINNER
    estimated_duration_hours: Optional[int] = None
    language: str = "en"
    enrollment_type: EnrollmentType = EnrollmentType.OPEN
    certification_enabled: bool = False


class CourseUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    learning_objectives: Optional[Dict[str, Any]] = None
    prerequisites: Optional[Dict[str, Any]] = None
    difficulty_level: Optional[DifficultyLevel] = None
    estimated_duration_hours: Optional[int] = None
    status: Optional[CourseStatus] = None
    enrollment_type: Optional[EnrollmentType] = None
    certification_enabled: Optional[bool] = None


class SectionCreate(SQLModel):
    title: str
    description: Optional[str] = None
    learning_objectives: Optional[Dict[str, Any]] = None
    order_index: int
    estimated_duration_minutes: Optional[int] = None
    is_optional: bool = False
    progression_type: ProgressionType = ProgressionType.SEQUENTIAL
    completion_criteria: Optional[Dict[str, Any]] = None


class ModuleCreate(SQLModel):
    title: str
    description: Optional[str] = None
    module_type: ModuleType
    order_index: int
    estimated_duration_minutes: Optional[int] = None
    is_required: bool = True
    prerequisites: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None


class VideoContentCreate(SQLModel):
    platform: VideoPlatform
    external_video_id: str
    video_url: str
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    embed_settings: Optional[Dict[str, Any]] = None


class DocumentContentCreate(SQLModel):
    platform: DocumentPlatform
    external_file_id: Optional[str] = None
    file_url: str
    embed_url: Optional[str] = None
    file_name: str
    file_type: str
    file_size_bytes: Optional[int] = None
    viewer_settings: Optional[Dict[str, Any]] = None


class QuizContentCreate(SQLModel):
    quiz_settings: Optional[Dict[str, Any]] = None
    passing_score: Optional[float] = None
    show_results: ShowResults = ShowResults.IMMEDIATE
    randomize_questions: bool = False


class QuizQuestionCreate(SQLModel):
    question_text: str
    question_type: QuestionType
    options: Optional[Dict[str, Any]] = None
    correct_answer: Optional[Dict[str, Any]] = None
    points: float = 1.0
    explanation: Optional[str] = None
    order_index: Optional[int] = None


# Update forward references
CourseWithSections.model_rebuild()
SectionWithModules.model_rebuild()
