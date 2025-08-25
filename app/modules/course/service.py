import uuid

from fastapi import HTTPException, status
from sqlalchemy import String
from sqlmodel import Session, cast, col, desc, select

from app.common.constants import PER_PAGE
from app.common.enum import (
    CourseStatus,
    DifficultyLevel,
    EnrollmentType,
    ModuleType,
    SortCoursesBy,
    VisibilityType,
)
from app.common.utils import paginate, slugify
from app.models.courses_model import (
    Course,
    CourseTag,
    DocumentContent,
    Module,
    ModuleAttachment,
    Section,
    Tag,
    VideoContent,
)
from app.models.user_model import Account
from app.schemas.courses import (
    CourseCreate,
    DocumentContentCreate,
    ModuleAttachmentCreate,
    ModuleCreate,
    SectionCreate,
    VideoContentCreate,
)


class CourseService:

    @staticmethod
    async def list_courses(
        title: str | None,
        sort: SortCoursesBy | None,
        level: DifficultyLevel | None,
        session: Session,
        page: int = 1,
        per_page: int = PER_PAGE,
    ):

        base_query = select(Course).where(
            Course.status == CourseStatus.PUBLISHED,
            Course.visibility == VisibilityType.PUBLIC,
            Course.enrollment_type == EnrollmentType.OPEN,
        )
        if title:
            base_query = base_query.where(col(Course.title).ilike(f"%{title}%"))

        if level:
            base_query = base_query.where(Course.difficulty_level == DifficultyLevel)

        if sort:
            base_query.order_by(desc(Course.comment_count))
        else:
            base_query.order_by(desc(Course.created_at))

        return paginate(session, base_query, page, per_page)

    @staticmethod
    async def list_by_tags(
        tag: str,
        session: Session,
        page: int = 1,
        per_page: int = PER_PAGE,
    ):

        statement = (
            select(Course)
            .join(CourseTag)
            .join(Tag)
            .where(
                col(Tag.name).in_(tag.lower()),
            )
            .distinct()  # Remove duplicates if course has multiple matching tags
        )

        return paginate(session, statement, page, per_page)

    @staticmethod
    async def popular_courses(
        session: Session,
        page: int = 1,
        per_page: int = PER_PAGE,
    ):
        statement = select(Course).order_by(
            desc(Course.average_rating),
            desc(Course.comment_count),
            desc(Course.enrollment_count),
            desc(Course.created_at),
        )

        return paginate(session, statement, page, per_page)

    @staticmethod
    async def create_course(
        session: Session, data: CourseCreate, current_user: Account
    ):
        cleaned_data = data.model_dump(exclude_unset=True)

        counter = 0
        orignal_slug = slugify(cleaned_data.get("title", ""))
        slug = orignal_slug

        while session.exec(select(Course).where(Course.slug == slug)):
            counter += 1
            slug = orignal_slug + f"-{counter}"

        course = Course(**cleaned_data, account_id=current_user.id, slug=slug)

        session.add(course)
        session.commit()
        session.refresh(course)
        return course

    @staticmethod
    async def create_section(
        session: Session, data: SectionCreate, current_user: Account
    ):
        course = session.get(Course, data.course_id)

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="course not found"
            )

        if course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        cleaned_data = data.model_dump(exclude_unset=True)

        section = Section(**cleaned_data)

        session.add(section)
        session.commit()
        session.refresh(section)

        return section

    @staticmethod
    async def create_module(
        session: Session, data: ModuleCreate, current_user: Account
    ):

        section = session.get(Section, data.section_id)

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
            )

        if section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        if (
            data.module_type == ModuleType.DISCUSSION
            or data.module_type == ModuleType.EXTERNAL_LINK
        ) and not (data.content_data and data.content_data.get("content")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='must have content_data set with {content: "string data"}',
            )

        cleaned_data = data.model_dump(exclude_unset=True)
        module = Module(**cleaned_data)

        session.add(module)
        session.commit()
        session.refresh(module)

        return module

    @staticmethod
    async def create_video(
        session: Session, data: VideoContentCreate, current_user: Account
    ):

        await CourseService._run_module_checks(
            session, data.module_id, current_user.id, ModuleType.VIDEO
        )

        cleaned_data = data.model_dump(exclude_unset=True)
        video = VideoContent(**cleaned_data)

        session.add(video)
        session.commit()
        session.refresh(video)

        return video

    @staticmethod
    async def create_document(
        session: Session, data: DocumentContentCreate, current_user: Account
    ):

        await CourseService._run_module_checks(
            session, data.module_id, current_user.id, ModuleType.DOCUMENT
        )

        cleaned_data = data.model_dump(exclude_unset=True)
        doc = DocumentContent(**cleaned_data)

        session.add(doc)
        session.commit()
        session.refresh(doc)

        return doc

    @staticmethod
    async def add_course_attachments(
        session: Session,
        attachements: list[ModuleAttachmentCreate],
        current_user: Account,
    ):

        for attachement in attachements:
            await CourseService._run_module_checks(
                session, attachement.module_id, current_user.id
            )

            cleaned_data = attachement.model_dump(exclude_unset=True)
            obj = ModuleAttachment(**cleaned_data)

            session.add(obj)
        session.commit()

    @staticmethod
    async def course_enrollment():
        pass

    @staticmethod
    async def add_tag_to_course():
        pass

    @staticmethod
    async def _run_module_checks(
        session: Session,
        module_id: uuid.UUID,
        user_id: uuid.UUID,
        module_type: ModuleType | None = None,
    ):
        results = session.exec(
            select(Module, Section).join(Section).where(Module.id == module_id)
        ).first()

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="module not found"
            )

        module, section = results

        if section.course.account_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        if module_type and module.module_type != module_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="can only create document if module type is document",
            )
