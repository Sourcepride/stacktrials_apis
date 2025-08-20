# Pydantic models for API responses (read models)
from datetime import datetime
from types import ModuleType
from typing import Any, Optional

from sqlmodel import SQLModel

from app.common.enum import (
    CourseStatus,
    DifficultyLevel,
    DocumentPlatform,
    EnrollmentType,
    ModuleProgressStatus,
    ProgressionType,
    QuestionType,
    ShowResults,
    VideoPlatform,
)


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
    sections: list["SectionRead"] = []


class SectionRead(SQLModel):
    id: int
    title: str
    description: Optional[str]
    order_index: int
    estimated_duration_minutes: Optional[int]
    is_optional: bool
    progression_type: ProgressionType


class SectionWithModules(SectionRead):
    modules: list["ModuleRead"] = []


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
    embed_settings: Optional[dict[str, Any]]


class DocumentContentRead(SQLModel):
    id: int
    platform: DocumentPlatform
    file_url: str
    embed_url: Optional[str]
    file_name: str
    file_type: str
    viewer_settings: Optional[dict[str, Any]]


class ModuleProgressRead(SQLModel):
    id: int
    account_id: int
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
    learning_objectives: Optional[dict[str, Any]] = None
    prerequisites: Optional[dict[str, Any]] = None
    difficulty_level: DifficultyLevel = DifficultyLevel.BEGINNER
    estimated_duration_hours: Optional[int] = None
    language: str = "en"
    enrollment_type: EnrollmentType = EnrollmentType.OPEN
    certification_enabled: bool = False


class CourseUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    learning_objectives: Optional[dict[str, Any]] = None
    prerequisites: Optional[dict[str, Any]] = None
    difficulty_level: Optional[DifficultyLevel] = None
    estimated_duration_hours: Optional[int] = None
    status: Optional[CourseStatus] = None
    enrollment_type: Optional[EnrollmentType] = None
    certification_enabled: Optional[bool] = None


class SectionCreate(SQLModel):
    title: str
    description: Optional[str] = None
    learning_objectives: Optional[dict[str, Any]] = None
    order_index: int
    estimated_duration_minutes: Optional[int] = None
    is_optional: bool = False
    progression_type: ProgressionType = ProgressionType.SEQUENTIAL
    completion_criteria: Optional[dict[str, Any]] = None


class ModuleCreate(SQLModel):
    title: str
    description: Optional[str] = None
    module_type: ModuleType
    order_index: int
    estimated_duration_minutes: Optional[int] = None
    is_required: bool = True
    prerequisites: Optional[dict[str, Any]] = None
    settings: Optional[dict[str, Any]] = None


class VideoContentCreate(SQLModel):
    platform: VideoPlatform
    external_video_id: str
    video_url: str
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    embed_settings: Optional[dict[str, Any]] = None


class DocumentContentCreate(SQLModel):
    platform: DocumentPlatform
    external_file_id: Optional[str] = None
    file_url: str
    embed_url: Optional[str] = None
    file_name: str
    file_type: str
    file_size_bytes: Optional[int] = None
    viewer_settings: Optional[dict[str, Any]] = None


class QuizContentCreate(SQLModel):
    quiz_settings: Optional[dict[str, Any]] = None
    passing_score: Optional[float] = None
    show_results: ShowResults = ShowResults.IMMEDIATE
    randomize_questions: bool = False


class QuizQuestionCreate(SQLModel):
    question_text: str
    question_type: QuestionType
    options: Optional[dict[str, Any]] = None
    correct_answer: Optional[dict[str, Any]] = None
    points: float = 1.0
    explanation: Optional[str] = None
    order_index: Optional[int] = None


# Update forward references
CourseWithSections.model_rebuild()
SectionWithModules.model_rebuild()
