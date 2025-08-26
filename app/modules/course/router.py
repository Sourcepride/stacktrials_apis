from fastapi import APIRouter, Body, Query
from fastapi.background import P
from typing_extensions import Annotated

from app.common.enum import DifficultyLevel, SortCoursesBy
from app.core.dependencies import CurrentActiveUser, SessionDep
from app.modules.course.service import CourseService
from app.schemas.courses import (
    CourseCommentCreate,
    CourseCommentRead,
    CourseCreate,
    CourseEnrollmentCreate,
    CourseEnrollmentRead,
    CourseRatingCreate,
    CourseRatingRead,
    CourseRead,
    CreateAttacment,
    DocumentContentCreate,
    DocumentContentRead,
    ModuleCreate,
    ModuleRead,
    PaginatedComments,
    PaginatedCourse,
    PaginatedRatings,
    SectionCreate,
    SectionRead,
    VideoContentCreate,
    VideoContentRead,
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


@router.delete("/section/{section_id}")
async def delete_section():
    pass


@router.get("/section/{section_id}")
async def get_section():
    pass


@router.post("/module", response_model=ModuleRead)
async def create_module(
    data: Annotated[ModuleCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_module(session, data, current_user)


@router.patch("/module/{module_id}")
async def update_module():
    pass


@router.delete("/module/{module_id}")
async def delete_module():
    pass


@router.get("/module/{module_id}")
async def get_module():
    pass


@router.post("/video", response_model=VideoContentRead)
async def create_video(
    data: Annotated[VideoContentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_video(session, data, current_user)


@router.patch("/video/{video_id}", response_model=VideoContentRead)
async def update_video(
    video_id: str,
    data: Annotated[VideoContentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return


@router.delete("/video/{video_id}")
async def delete_video(
    video_id: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return


@router.post("/document", response_model=DocumentContentRead)
async def create_document(
    data: Annotated[DocumentContentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_document(session, data, current_user)


@router.patch("/document/{document_id}", response_model=DocumentContentRead)
async def update_document(
    document_id: str,
    data: Annotated[DocumentContentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return


@router.delete("document/{document_id}")
async def delete_document(
    document_id: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return


@router.post("/add-attachments")
async def add_attachment(
    data: Annotated[CreateAttacment, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.add_course_attachments(session, data.data, current_user)


@router.delete("/remove-attachment/{id}")
async def remove_attachment(
    id: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return


@router.get("/enroll", response_model=CourseEnrollmentRead)
async def create_enrollment(
    data: Annotated[CourseEnrollmentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_enrollment(session, data, current_user)


@router.post("/ratings", response_model=CourseRatingRead)
async def create_rating(
    data: Annotated[CourseRatingCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_course_rating(session, data, current_user)


@router.post("/comments", response_model=CourseCommentRead)
async def create_comment(
    data: Annotated[CourseCommentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_comment(session, data, current_user)


@router.patch("/comments/{id}", response_model=CourseCommentRead)
async def update_comment(
    id: str,
    data: Annotated[CourseCommentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return


@router.get("/{course_id}/{slug}/ratings", response_model=PaginatedRatings)
async def list_ratings(
    session: SessionDep,
):
    return


@router.get("/{course_id}/{slug}/comments", response_model=PaginatedComments)
async def list_comments(
    session: SessionDep,
):
    return


@router.get("/{course_id}/{slug}")
async def course_detail(course_id: str, couse_slug: str):
    pass


@router.patch("/{course_id}/{course_slug}")
async def update_course(course_id: str, couse_slug: str):
    pass


@router.delete("/{course_id}/{course_slug}")
async def delete_course(course_id: str, couse_slug: str):
    pass


@router.get("/{course_id}/{slug}/content/minmal")
async def course_content(course_id: str, slug: str, session: SessionDep):
    # open to everyone
    pass


@router.get("/{course_id}/{slug}/content/full")
async def full_course_content(
    course_id: str, slug: str, session: SessionDep, curren_user: CurrentActiveUser
):
    # user must have enrolled first
    pass
