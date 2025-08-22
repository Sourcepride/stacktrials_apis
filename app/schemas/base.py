# Pydantic models for API responses (read models)
from datetime import datetime
from types import ModuleType
from typing import Any, Optional

from pydantic import BaseModel
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
