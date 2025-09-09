from calendar import c

from fastapi import APIRouter, Body, Query
from fastapi.background import P
from typing_extensions import Annotated

from app.common.enum import DifficultyLevel, SortCoursesBy
from app.core.dependencies import CurrentActiveUser, CurrentActiveUserSilent, SessionDep
from app.modules.course.service import CourseService
from app.schemas.courses import (
    CourseCommentCreate,
    CourseCommentRead,
    CourseCommentUpdate,
    CourseContentReadFull,
    CourseContentReadMin,
    CourseCreate,
    CourseEnrollmentCreate,
    CourseEnrollmentRead,
    CourseRatingCreate,
    CourseRatingRead,
    CourseRead,
    CourseUpdate,
    CreateAttacment,
    DocumentContentCreate,
    DocumentContentRead,
    DocumentContentUpdate,
    ModuleCreate,
    ModuleRead,
    ModuleReadMin,
    ModuleUpdate,
    PaginatedComments,
    PaginatedCourse,
    PaginatedRatings,
    SectionCreate,
    SectionRead,
    SectionUpdate,
    VideoContentCreate,
    VideoContentRead,
    VideoContentUpdate,
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
    language: Annotated[str | None, Query()] = None,
    page: int | None = None,
):
    return await CourseService.list_courses(
        q, sort, level, session, language, page or 1
    )


@router.get("/tags/{name}", response_model=PaginatedCourse)
async def by_tags(session: SessionDep, name: str, page: int | None = None):
    return await CourseService.list_by_tags(name, session, page or 1)


@router.get("/popular", response_model=PaginatedCourse)
async def popular_courses(session: SessionDep, page: int | None = None):
    return await CourseService.popular_courses(session, page or 1)


@router.post("/", response_model=CourseRead, status_code=201)
async def create_course(
    data: Annotated[CourseCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_course(session, data, current_user)


@router.post("/section", response_model=SectionRead, status_code=201)
async def create_section(
    data: Annotated[SectionCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_section(session, data, current_user)


@router.patch("/section/{section_id}", response_model=SectionRead)
async def update_section(
    section_id: str,
    data: Annotated[SectionUpdate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.update_section(session, section_id, data, current_user)


@router.delete("/section/{section_id}", status_code=204)
async def delete_section(
    section_id: str, session: SessionDep, current_user: CurrentActiveUser
):
    return await CourseService.delete_section(session, section_id, current_user)


@router.get("/section/{section_id}", response_model=SectionRead)
async def get_section(section_id: str, session: SessionDep):
    return await CourseService.get_section(session, section_id)


@router.post("/module", response_model=ModuleRead, status_code=201)
async def create_module(
    data: Annotated[ModuleCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_module(session, data, current_user)


@router.patch("/module/{module_id}", response_model=ModuleRead)
async def update_module(
    module_id: str,
    data: Annotated[ModuleUpdate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.update_module(session, module_id, data, current_user)


@router.delete("/module/{module_id}", status_code=204)
async def delete_module(
    module_id: str, session: SessionDep, current_user: CurrentActiveUser
):
    return await CourseService.delete_module(session, module_id, current_user)


@router.get("/module/{module_id}", response_model=ModuleReadMin)
async def get_module(module_id: str, session: SessionDep):
    return await CourseService.get_module(session, module_id)


@router.post("/video", response_model=VideoContentRead, status_code=201)
async def create_video(
    data: Annotated[VideoContentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_video(session, data, current_user)


@router.patch("/video/{video_id}", response_model=VideoContentRead)
async def update_video(
    video_id: str,
    data: Annotated[VideoContentUpdate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.update_video(session, video_id, data, current_user)


@router.delete("/video/{video_id}", status_code=204)
async def delete_video(
    video_id: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.delete_video(session, video_id, current_user)


@router.post("/document", response_model=DocumentContentRead, status_code=201)
async def create_document(
    data: Annotated[DocumentContentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_document(session, data, current_user)


@router.patch("/document/{document_id}", response_model=DocumentContentRead)
async def update_document(
    document_id: str,
    data: Annotated[DocumentContentUpdate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.update_document(session, document_id, data, current_user)


@router.delete("document/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.delete_document(session, document_id, current_user)


@router.post("/add-attachments")
async def add_attachment(
    data: Annotated[CreateAttacment, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.add_course_attachments(session, data.data, current_user)


@router.delete("/remove-attachment/{id}", status_code=204)
async def remove_attachment(
    id: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.remove_course_attachments(session, id, current_user)


@router.post("/enroll", response_model=CourseEnrollmentRead)
async def create_enrollment(
    data: Annotated[CourseEnrollmentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_enrollment(session, data, current_user)


@router.post("/ratings", response_model=CourseRatingRead, status_code=201)
async def create_rating(
    data: Annotated[CourseRatingCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_course_rating(session, data, current_user)


@router.post("/comments", response_model=CourseCommentRead, status_code=201)
async def create_comment(
    data: Annotated[CourseCommentCreate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.create_comment(session, data, current_user)


@router.patch("/comments/{id}", response_model=CourseCommentRead)
async def update_comment(
    id: str,
    data: Annotated[CourseCommentUpdate, Body()],
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.update_comment(session, id, data, current_user)


@router.get("/{course_id}/enroll", response_model=CourseEnrollmentRead)
async def get_enrollment(
    course_id: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await CourseService.get_enrollment(course_id, session, current_user)


@router.get("/{course_id}/ratings", response_model=PaginatedRatings)
async def list_ratings(
    course_id: str, session: SessionDep, page: Annotated[int | None, Query()] = None
):
    return await CourseService.list_ratings(course_id, session, page or 1)


@router.get("/{course_id}/comments", response_model=PaginatedComments)
async def list_comments(
    course_id: str,
    session: SessionDep,
    current_user: CurrentActiveUserSilent,
    page: Annotated[int | None, Query()] = None,
):
    return await CourseService.list_comments(
        course_id, session, page or 1, current_user
    )


@router.get("/{comment_id}/replies", response_model=PaginatedComments)
async def list_replies(
    comment_id: str,
    session: SessionDep,
    current_user: CurrentActiveUserSilent,
    page: Annotated[int | None, Query()] = None,
):
    return await CourseService.list_replies(
        comment_id, session, page or 1, current_user
    )


@router.patch("/{comment_id}/like-unlike")
async def like_unlike(
    comment_id: str, session: SessionDep, current_user: CurrentActiveUser
):
    return await CourseService.like_unlike(comment_id, session, current_user)


@router.get("/{slug}/content/minimal", response_model=CourseContentReadMin)
async def course_content(slug: str, session: SessionDep):
    # open to everyone
    return await CourseService.course_content(session, slug)


@router.get("/{slug}/content/full", response_model=CourseContentReadFull)
async def full_course_content(
    slug: str, session: SessionDep, curren_user: CurrentActiveUser
):
    # user must have enrolled first
    return await CourseService.course_content_full(session, slug, curren_user)


@router.delete("/{course_id}/{course_slug}", status_code=204)
async def delete_course(course_id: str, course_slug: str, session: SessionDep):
    return


@router.get("/{slug}", response_model=CourseRead)
async def course_detail(slug: str, session: SessionDep):
    return await CourseService.course_detail(session, slug)


@router.patch("/{course_slug}", response_model=CourseRead)
async def update_course(
    course_slug: str,
    session: SessionDep,
    data: Annotated[CourseUpdate, Body()],
    current_user: CurrentActiveUser,
):
    return await CourseService.update_course(session, course_slug, data, current_user)
