import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, asc, col, desc, select

from app.common.constants import PER_PAGE
from app.common.enum import (
    CourseStatus,
    DifficultyLevel,
    EnrollmentType,
    ModuleProgressStatus,
    ModuleType,
    SortCoursesBy,
    VisibilityType,
)
from app.common.utils import paginate, slugify
from app.core.dependencies import CurrentActiveUser
from app.models.comments_model import Comment, Rating
from app.models.courses_model import (
    Course,
    CourseEnrollment,
    CourseProgress,
    CourseTag,
    DocumentContent,
    Module,
    ModuleAttachment,
    Section,
    Tag,
    VideoContent,
)
from app.models.user_model import Account
from app.modules import course
from app.schemas.courses import (
    CourseCommentCreate,
    CourseCommentUpdate,
    CourseCreate,
    CourseEnrollmentCreate,
    CourseRatingCreate,
    CourseUpdate,
    DocumentContentCreate,
    DocumentContentUpdate,
    ModuleAttachmentCreate,
    ModuleCreate,
    ModuleUpdate,
    SectionCreate,
    SectionUpdate,
    VideoContentCreate,
    VideoContentUpdate,
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
            # Course.status == CourseStatus.PUBLISHED,
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

        slug = CourseService._generate_course_slug(
            cleaned_data.get("title", ""), session
        )

        course = Course(**cleaned_data, account_id=current_user.id, slug=slug)

        session.add(course)
        session.commit()
        session.refresh(course)
        return course

    @staticmethod
    async def update_course(
        session: Session, id: str, slug: str, data: CourseUpdate, current_user: Account
    ):
        course = CourseService._get_course_or_404(id, slug, session)

        if course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        cleaned_data = data.model_dump(exclude_unset=True)
        slug = course.slug
        title = cleaned_data.get("title", "")

        if course.title != title:
            slug = CourseService._generate_course_slug(title, session)

        course.sqlmodel_update({**cleaned_data, "slug": slug})

        session.add(course)
        session.commit()
        session.refresh(course)
        return course

    @staticmethod
    async def course_detail(session: Session, id: str, slug: str):
        course = CourseService._get_course_or_404(id, slug, session)

        return course

    @staticmethod
    async def course_content(session: Session, id: str, slug: str):
        course = CourseService._get_course_or_404(id, slug, session)
        sections = session.exec(
            select(Section)
            .where(Section.course_id == course.id)
            .order_by(asc(Section.order_index))
        ).all()

        return {**course.model_dump(), sections: sections}

    @staticmethod
    async def course_content_full(
        session: Session, id: str, slug: str, current_user: Account
    ):
        course = CourseService._get_course_or_404(id, slug, session)
        course_enrollment = session.exec(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == id,
                CourseEnrollment.account_id == current_user.id,
            )
        ).first()

        if not course_enrollment:
            raise HTTPException(403, "you can only access courses you enrolled for")
        sections = session.exec(
            select(Section)
            .where(Section.course_id == course.id)
            .order_by(asc(Section.order_index))
        ).all()

        return {**course.model_dump(), sections: sections}

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
    async def update_section(
        session: Session, id: str, data: SectionUpdate, current_user: Account
    ):

        section = session.get(Section, id)

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
            )

        if section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        cleaned_data = data.model_dump(exclude_unset=True)
        section.sqlmodel_update(cleaned_data)

        session.add(section)
        session.commit()
        session.refresh(section)

        return section

    @staticmethod
    async def get_section(session: Session, section_id: str):
        section = session.get(Section, section_id)

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
            )

        return section

    @staticmethod
    async def delete_section(session: Session, section_id: str, current_user: Account):
        section = session.get(Section, section_id)

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
            )

        if section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        session.delete(section)
        session.commit()

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
    async def update_module(
        session: Session, id: str, data: ModuleUpdate, current_user: Account
    ):

        module = session.get(Module, id)

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="module not found"
            )

        if module.section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        cleaned_data = data.model_dump(exclude_unset=True)
        module.sqlmodel_update(**cleaned_data)

        session.add(module)
        session.commit()
        session.refresh(module)

        return module

    @staticmethod
    async def delete_module(session: Session, module_id: str, current_user: Account):
        module = session.get(Module, module_id)

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="module not found"
            )

        if module.section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        session.delete(module)
        session.commit()

    @staticmethod
    async def get_module(
        session: Session,
        module_id: str,
    ):
        module = session.get(Module, module_id)

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="module not found"
            )

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
    async def update_video(
        session: Session, id: str, data: VideoContentUpdate, current_user: Account
    ):

        video = session.get(VideoContent, id)

        if not video:
            raise HTTPException(404, "video content does not exist")

        await CourseService._run_module_checks(
            session, video.module_id, current_user.id, ModuleType.VIDEO
        )

        cleaned_data = data.model_dump(exclude_unset=True)
        video.sqlmodel_update(**cleaned_data)

        session.add(video)
        session.commit()
        session.refresh(video)

        return video

    @staticmethod
    async def delete_video(session: Session, id: str, current_user: Account):

        video = session.get(VideoContent, id)

        if not video:
            raise HTTPException(404, "video content does not exist")

        await CourseService._run_module_checks(
            session, video.module_id, current_user.id, ModuleType.VIDEO
        )

        session.delete(video)
        session.commit()

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
    async def update_document(
        session: Session, id: str, data: DocumentContentUpdate, current_user: Account
    ):

        doc = session.get(DocumentContent, id)

        if not doc:
            raise HTTPException(404, "document does not exist")

        await CourseService._run_module_checks(
            session, doc.module_id, current_user.id, ModuleType.DOCUMENT
        )

        cleaned_data = data.model_dump(exclude_unset=True)
        doc.sqlmodel_update(**cleaned_data)

        session.add(doc)
        session.commit()
        session.refresh(doc)

        return doc

    @staticmethod
    async def delete_document(session: Session, id: str, current_user: Account):

        doc = session.get(DocumentContent, id)

        if not doc:
            raise HTTPException(404, "document does not exist")

        await CourseService._run_module_checks(
            session, doc.module_id, current_user.id, ModuleType.DOCUMENT
        )

        session.delete(doc)
        session.commit()

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
    async def remove_course_attachments(
        session: Session,
        attachment_id: str,
        current_user: Account,
    ):

        attachment = session.get(ModuleAttachment, attachment_id)
        if not attachment:
            raise HTTPException(404, "attachment does not exist")

        section = session.get(Section, attachment.module.section_id)

        assert section is not None

        if section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        session.delete(attachment)
        session.commit()

    @staticmethod
    async def create_enrollment(
        session: Session,
        data: CourseEnrollmentCreate,
        current_user: Account,
    ):

        course = session.get(Course, data.course_id)

        # TODO: before enrollment check for criteria like pay for paid courses

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="course not found"
            )

        cleaned_data = data.model_dump(exclude_unset=True)
        enrollment = CourseEnrollment(**cleaned_data)
        enrollment.account_id = current_user.id

        progress = CourseProgress(
            account_id=current_user.id,
            course_id=course.id,
            start_time=datetime.now(timezone.utc),
            status=ModuleProgressStatus.IN_PROGRESS,
            last_active_date=datetime.now(timezone.utc),
        )

        session.add(enrollment)
        session.add(progress)
        session.commit()
        session.refresh(enrollment)

        return enrollment

    @staticmethod
    async def create_course_rating(
        session: Session,
        data: CourseRatingCreate,
        current_user: Account,
    ):
        course = session.get(Course, data.course_id)

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="course not found"
            )

        enrollment = session.exec(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == data.course_id,
                CourseEnrollment.account_id == current_user.id,
            )
        ).first()

        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot rate a course you have not enrolled for",
            )

        cleaned_data = data.model_dump(exclude_unset=True)
        rating = Rating(**cleaned_data)
        rating.account_id = current_user.id
        # this is to support replies
        comment = Comment(
            message=data.message,
            is_rating=True,
            course_id=data.comment_id,
            creator_id=current_user.id,
        )

        session.add(comment)
        session.commit()
        session.refresh(comment)

        rating.comment_id = comment.id

        session.add(rating)
        session.commit()
        session.refresh(rating)

        return rating

    @staticmethod
    async def list_ratings(
        course_id: str, session: Session, page: int = 1, per_page: int = PER_PAGE
    ):

        query = select(Rating).join(Comment).where(Rating.course_id == course_id)

        return paginate(session, query, page, per_page)

    @staticmethod
    async def create_comment(
        session: Session,
        data: CourseCommentCreate,
        current_user: Account,
    ):
        course = session.get(Course, data.course_id)

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="course not found"
            )

        if not data.reply_to_id:
            comment = Comment(**data.model_dump(exclude_unset=True))
            comment.is_rating = False
            comment.creator_id = current_user.id
            session.add(comment)
            session.commit()
            session.refresh(comment)
            return comment

        """
            course_id
            reply_to
                -  get the comment 
                    if it a reply_to take the id of that reply_to

            course
                - comment A
                    -  comment B 
                    -  comment C  [mention_id  @comment B ]  
        """

        comment_replied = session.get(Comment, data.reply_to_id)

        if not comment_replied:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="comment not found"
            )

        reply_to_id = (
            comment_replied.reply_to_id
            if comment_replied.reply_to_id
            else comment_replied.id
        )

        comment = Comment(**data.model_dump(exclude_unset=True))
        comment.is_rating = (
            comment_replied.is_rating
        )  # replies to ratings are ratings comments
        comment.mention_id = comment_replied.creator_id
        comment.creator_id = current_user.id
        comment.reply_to_id = reply_to_id

        # comment_count increment
        upgraded_parent = session.get(Comment, reply_to_id)
        assert upgraded_parent is not None
        upgraded_parent.comment_count += 1

        session.add(comment)
        session.add(upgraded_parent)
        session.commit()
        session.refresh(comment)

        return comment

    @staticmethod
    async def update_comment(
        session: Session,
        id: str,
        data: CourseCommentUpdate,
        current_user: Account,
    ):
        comment = session.get(Comment, id)

        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="comment not found"
            )
        if comment.creator_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        message = data.message or comment.message

        comment.sqlmodel_update({"message": message})

        if comment.is_rating:
            rating = session.exec(
                select(Rating).where(Rating.comment_id == comment.id)
            ).first()
            if rating:
                rating.message = message
                session.add(rating)

        session.add(comment)
        session.commit()
        session.refresh(comment)
        return comment

    @staticmethod
    async def list_comments(
        course_id: str, session: Session, page: int = 1, per_page: int = PER_PAGE
    ):
        query = select(Comment).where(
            Comment.course_id == course_id, Comment.is_rating == False
        )

        return paginate(session, query, page, per_page)

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

    @staticmethod
    def _get_course_or_404(course_id: str, slug: str, session: Session):
        course = session.exec(
            select(Course).where(Course.id == course_id, Course.slug == slug)
        ).first()
        if not course:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "course not found")
        return course

    @staticmethod
    def _generate_course_slug(title: str, session: Session):
        counter = 0
        orignal_slug = slugify(title)
        slug = orignal_slug

        while bool(session.exec(select(Course).where(Course.slug == slug)).first()):
            counter += 1
            slug = orignal_slug + f"-{counter}"

        return slug
