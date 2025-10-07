from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentActiveUser, SessionDep
from app.modules.creator.service import CreatorService
from app.schemas.courses import CreatorStat, PaginatedCourse

router = APIRouter()


@router.get("/courses/stats", response_model=CreatorStat)
async def courses_stat(currentUser: CurrentActiveUser, session: SessionDep):
    return await CreatorService.course_stat(currentUser, session)


@router.get("/created", response_model=PaginatedCourse)
async def created(
    currentUser: CurrentActiveUser,
    session: SessionDep,
    page: int | None = None,
    title: Annotated[str | None, Query()] = None,
):
    return await CreatorService.created_videos(title, currentUser, session, page or 1)


# @router.get("/earnings")
# async def earnings():
#     pass
