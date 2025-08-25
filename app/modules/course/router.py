from fastapi import APIRouter, Body, Query
from fastapi.background import P
from typing_extensions import Annotated

from app.common.enum import DifficultyLevel, SortCoursesBy
from app.core.dependencies import CurrentActiveUser, SessionDep
from app.modules.course.service import CourseService
from app.schemas.courses import (
    CourseCreate,
    CourseRead,
    PaginatedCourse,
    SectionCreate,
    SectionRead,
)

router = APIRouter()


@router.get("/", response_model=PaginatedCourse)
async def list_courses(
    session: SessionDep,
    q: Annotated[str | None, Query(description="search by title")] = None,
    sort: Annotated[
        SortCoursesBy | None, Query(description="sort by (value:  most_enrolled)")
    ] = None,
    level: Annotated[DifficultyLevel | None, Query()] = None,
    page: int | None = None,
):
    return await CourseService.list_courses(q, sort, level, session, page or 1)


@router.get("/tags/{name}", response_model=PaginatedCourse)
async def by_tags(session: SessionDep, name: str, page: int | None = None):
    return await CourseService.list_by_tags(name, session, page or 1)


@router.get("/popular", response_model=PaginatedCourse)
async def popular_courses(session: SessionDep, page: int | None = None):
    return await CourseService.popular_courses(session, page or 1)


@router.post("/", response_model=CourseRead)
async def create_course(
    data: Annotated[CourseCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_course(session, data, current_user)


@router.patch("/")
async def update_course():
    pass


@router.post("/section", response_model=SectionRead)
async def create_section(
    data: Annotated[SectionCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_section(session, data, current_user)


@router.patch("/section/{section_id}")
async def update_section():
    pass


@router.get("/section/{section_id}")
async def get_section():
    pass


@router.post("/module")
async def create_module():
    pass


@router.patch("/module/{module_id}")
async def update_module():
    pass


@router.get("/{course_id}/{slug}")
async def course_detail():
    pass


@router.get("/{course_id}/{slug}")
async def course_content():
    pass


@router.get("/{course_id}/{slug}")
async def enroll():
    pass
