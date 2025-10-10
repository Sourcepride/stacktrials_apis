from fastapi import APIRouter, Body
from typing_extensions import Annotated

from app.core.dependencies import CurrentActiveUser, SessionDep
from app.models.user_model import Account
from app.modules.student.service import StudentService
from app.schemas.courses import (
    CourseEnrollmentRead,
    CourseProgressRead,
    IncrementProgress,
    LearnerStat,
    PaginatedEnrolledCourses,
    ToggleModuleCompleted,
)

router = APIRouter()


@router.get("/enrolled", response_model=PaginatedEnrolledCourses)
async def enrolled(
    current_user: CurrentActiveUser, session: SessionDep, page: int | None = None
):
    return await StudentService.enrolled(current_user, session, page or 1)


@router.post("/increment-progress", response_model=CourseProgressRead)
async def increment_progress(
    current_user: CurrentActiveUser,
    session: SessionDep,
    data: Annotated[IncrementProgress, Body()],
):
    return await StudentService.increment_progress(
        current_user, session, data.module_id
    )


@router.post("/toggle-module-completed", response_model=CourseEnrollmentRead)
async def toggle_module_completed(
    current_user: CurrentActiveUser,
    session: SessionDep,
    data: Annotated[ToggleModuleCompleted, Body()],
):
    return await StudentService.toggle_module_completion_status(
        current_user, session, data.module_id, data.status
    )


@router.get("/dashboard", response_model=LearnerStat)
async def dashboard(current_user: CurrentActiveUser, session: SessionDep):
    return await StudentService.dashboard_stats(current_user, session)
