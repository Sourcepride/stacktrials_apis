from fastapi import APIRouter, Body
from typing_extensions import Annotated

from app.core.dependencies import SessionDep
from app.models.user_model import Account
from app.modules.student.service import StudentService
from app.schemas.courses import IncrementProgress, ToggleModuleCompleted

router = APIRouter()


@router.get("/enrolled")
async def enrolled(current_user: Account, session: SessionDep, page: int | None = None):
    return await StudentService.enrolled(current_user, session, page or 1)


@router.post("/increment-progress")
async def increment_progress(
    current_user: Account,
    session: SessionDep,
    data: Annotated[IncrementProgress, Body()],
):
    return await StudentService.increment_progress(
        current_user, session, data.module_id
    )


@router.post("/toggle-module-completed")
async def toggle_module_completed(
    current_user: Account,
    session: SessionDep,
    data: Annotated[ToggleModuleCompleted, Body()],
):
    return await StudentService.toggle_module_completion_status(
        current_user, session, data.module_id, data.status
    )


@router.get("/dasboard")
async def dashboard(current_user: Account, session: SessionDep):
    return await StudentService.dashboard_stats(current_user, session)
