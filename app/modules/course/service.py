import uuid
from datetime import datetime, timezone
from typing import Any, Optional, cast

from fastapi import HTTPException, status
from pydantic import HttpUrl
from sqlalchemy import BinaryExpression, text
from sqlmodel import asc, col, desc, func, or_, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.common.constants import PER_PAGE
from app.common.enum import (
    CourseStatus,
    DifficultyLevel,
    DocumentPlatform,
    EnrollmentType,
    MediaType,
    ModuleProgressStatus,
    ModuleType,
    SortCoursesBy,
    VideoPlatform,
    VisibilityType,
)
from app.common.utils import paginate, slugify
from app.core.dependencies import CurrentActiveUser, CurrentActiveUserSilent
from app.models.comments_model import Comment, CommentLike, Rating
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
from app.modules.media.router import validate_document_url
from app.modules.media.service import URLValidator
from app.schemas.courses import (
    CourseCommentCreate,
    CourseCommentRead,
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
from app.schemas.media import DocumentItem


class CourseService:

    @staticmethod
    async def explore_courses(
        session: AsyncSession,
        q: str | None = None,
        tags: list[str] | None = None,
        level: DifficultyLevel | None = None,
        language: str | None = None,
        sort: SortCoursesBy | None = None,
        page: int = 1,
        per_page: int = PER_PAGE,
    ):
        """
        Combined explore filter: search, tags, difficulty, language, sorting.
        """
        base_query = (
            select(Course)
            .where(
                Course.status == CourseStatus.PUBLISHED,
                Course.visibility == VisibilityType.PUBLIC,
            )
            .group_by(Course.id)
        )

        if q:
            pattern = f"%{q.lower()}%"
            base_query = base_query.where(
                or_(
                    func.lower(Course.title).like(pattern),
                    func.lower(Course.description).like(pattern),
                )
            )

        # 🎯 Filter by tags
        if tags:
            tag_names = [t.strip().lower() for t in tags if t.strip()]
            if tag_names:
                base_query = (
                    base_query.join(CourseTag)
                    .join(Tag)
                    .where(col(Tag.name).in_(tag_names))
                    .group_by(Course.id)
                )

        if level:
            base_query = base_query.where(Course.difficulty_level == level)

        if language:
            base_query = base_query.where(Course.language == language)

        #  Sorting logic
        if sort == SortCoursesBy.MOST_ENROLLED:
            base_query = base_query.order_by(desc(Course.enrollment_count))
        elif sort == SortCoursesBy.TOP_RATED:
            base_query = base_query.order_by(desc(Course.average_rating))
        else:
            base_query = base_query.order_by(desc(Course.created_at))

        return await paginate(session, base_query, page, per_page)

    @staticmethod
    async def list_courses(
        title: str | None,
        sort: SortCoursesBy | None,
        level: DifficultyLevel | None,
        session: AsyncSession,
        language: str | None,
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
            base_query = base_query.where(Course.difficulty_level == level)

        if language:
            base_query = base_query.where(Course.language == language)

        if sort == SortCoursesBy.MOST_ENROLLED:
            base_query.order_by(desc(Course.comment_count))
        elif sort == SortCoursesBy.TOP_RATED:
            base_query.order_by(desc(Course.average_rating))
        else:
            base_query.order_by(desc(Course.created_at))

        return await paginate(session, base_query, page, per_page)

    @staticmethod
    async def list_by_tags(
        tag: str,
        session: AsyncSession,
        page: int = 1,
        per_page: int = PER_PAGE,
    ):

        statement = (
            select(Course)
            .join(CourseTag)
            .join(Tag)
            .where(
                col(Tag.name).in_(tag.lower()),
                Course.status == CourseStatus.PUBLISHED,
                Course.visibility == VisibilityType.PUBLIC,
            )
            .distinct()  # Remove duplicates if course has multiple matching tags
        )

        return await paginate(session, statement, page, per_page)

    @staticmethod
    async def popular_courses(
        session: AsyncSession,
        page: int = 1,
        per_page: int = PER_PAGE,
    ):
        statement = (
            select(Course)
            .where(
                Course.status == CourseStatus.PUBLISHED,
                Course.visibility == VisibilityType.PUBLIC,
            )
            .order_by(
                desc(Course.average_rating),
                desc(Course.comment_count),
                desc(Course.enrollment_count),
                desc(Course.created_at),
            )
        )

        return await paginate(session, statement, page, per_page)

    @staticmethod
    async def create_course(
        session: AsyncSession, data: CourseCreate, current_user: Account
    ):
        cleaned_data = data.model_dump(exclude_unset=True)

        slug = await CourseService._generate_course_slug(
            cleaned_data.get("title", ""), session
        )

        tags = cleaned_data.pop("tags", [])
        course = Course(**cleaned_data, account_id=current_user.id, slug=slug)

        session.add(course)
        await session.commit()
        await session.refresh(course)

        if tags:
            await CourseService._sync_course_tags(session, course, tags)

        return course

    @staticmethod
    async def update_course(
        session: AsyncSession, slug: str, data: CourseUpdate, current_user: Account
    ):
        course = await CourseService._get_course_or_404(slug, session, current_user)

        cleaned_data = data.model_dump(exclude_unset=True)
        slug = course.slug
        title = cleaned_data.get("title", "")

        if title and course.title != title:
            slug = await CourseService._generate_course_slug(title, session)

        tags = cleaned_data.pop("tags", None)
        course.sqlmodel_update({**cleaned_data, "slug": slug})
        course.updated_at = datetime.now(tz=timezone.utc)

        session.add(course)
        await session.commit()
        await session.refresh(course)

        if tags is not None:
            await CourseService._sync_course_tags(session, course, tags)
        return course

    @staticmethod
    async def course_detail(
        session: AsyncSession, slug: str, currentUser: Optional[Account] = None
    ):
        course = await CourseService._get_course_or_404(slug, session, currentUser)

        return course

    @staticmethod
    async def course_content(session: AsyncSession, slug: str):
        course = await CourseService._get_course_or_404(slug, session)
        return course

    @staticmethod
    async def course_content_full(
        session: AsyncSession, slug: str, current_user: Account
    ):
        course = await CourseService._get_course_or_404(slug, session, current_user)
        course_enrollment = (
            await session.exec(
                select(CourseEnrollment).where(
                    CourseEnrollment.course_id == course.id,
                    CourseEnrollment.account_id == current_user.id,
                )
            )
        ).first()

        if not course_enrollment and course.account_id != current_user.id:
            raise HTTPException(403, "you can only access courses you enrolled for")

        return course

    @staticmethod
    async def create_section(
        session: AsyncSession, data: SectionCreate, current_user: Account
    ):
        course = await session.get(Course, data.course_id)

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
        course.updated_at = datetime.now(tz=timezone.utc)

        session.add(section)
        await session.commit()
        await session.refresh(section)

        return section

    @staticmethod
    async def update_section(
        session: AsyncSession, id: str, data: SectionUpdate, current_user: Account
    ):

        section = await session.get(Section, id)

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
            )

        if section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        # TODO:  upate updated_at for course

        cleaned_data = data.model_dump(exclude_unset=True)
        section.sqlmodel_update(cleaned_data)
        section.course.updated_at = datetime.now(tz=timezone.utc)

        session.add(section)
        await session.commit()
        await session.refresh(section)

        return section

    @staticmethod
    async def get_section(session: AsyncSession, section_id: str):
        section = await session.get(Section, section_id)

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
            )

        return section

    @staticmethod
    async def delete_section(
        session: AsyncSession, section_id: str, current_user: Account
    ):
        section = await session.get(Section, section_id)

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
            )

        if section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        await session.delete(section)
        await session.commit()

    @staticmethod
    async def create_module(
        session: AsyncSession, data: ModuleCreate, current_user: Account
    ):

        section = await session.get(Section, data.section_id)

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
        section.course.updated_at = datetime.now(tz=timezone.utc)

        session.add(module)
        await session.commit()
        await session.refresh(module)

        return module

    @staticmethod
    async def update_module(
        session: AsyncSession, id: str, data: ModuleUpdate, current_user: Account
    ):

        module = await session.get(Module, id)

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="module not found"
            )

        if module.section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        # TODO:  upate updated_at for course

        cleaned_data = data.model_dump(exclude_unset=True)
        module.sqlmodel_update(cleaned_data)
        module.section.course.updated_at = datetime.now(tz=timezone.utc)

        session.add(module)
        await session.commit()
        await session.refresh(module)

        return module

    @staticmethod
    async def delete_module(
        session: AsyncSession, module_id: str, current_user: Account
    ):
        module = await session.get(Module, module_id)

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="module not found"
            )

        if module.section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        await session.delete(module)
        await session.commit()

    @staticmethod
    async def get_module(
        session: AsyncSession,
        module_id: str,
    ):
        module = await session.get(Module, module_id)

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="module not found"
            )

        return module

    @staticmethod
    async def get_full_module(
        session: AsyncSession, module_id: str, current_user: Account
    ):
        module = await session.get(Module, module_id)

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="module not found"
            )

        course_enrollment = (
            await session.exec(
                select(CourseEnrollment).where(
                    CourseEnrollment.course_id == module.section.course_id,
                    CourseEnrollment.account_id == current_user.id,
                )
            )
        ).first()

        if (
            module.section.course.account_id != current_user.id
            and not course_enrollment
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        return module

    @staticmethod
    async def create_video(
        session: AsyncSession, data: VideoContentCreate, current_user: Account
    ):

        await CourseService._run_module_checks(
            session, data.module_id, current_user.id, ModuleType.VIDEO
        )
        validator_resp = await CourseService._validate_video(
            data.video_url, data.platform
        )

        cleaned_data = data.model_dump(exclude_unset=True)
        video = VideoContent(**cleaned_data)
        video.embed_url = validator_resp.embed_url

        session.add(video)
        await session.commit()
        await session.refresh(video)

        return video

    @staticmethod
    async def update_video(
        session: AsyncSession, id: str, data: VideoContentUpdate, current_user: Account
    ):

        video = await session.get(VideoContent, id)

        if not video:
            raise HTTPException(404, "video content does not exist")

        await CourseService._run_module_checks(
            session, video.module_id, current_user.id, ModuleType.VIDEO
        )

        validator_resp = await CourseService._validate_video(
            data.video_url or video.video_url, data.platform or video.platform
        )

        cleaned_data = data.model_dump(exclude_unset=True)
        video.sqlmodel_update(cleaned_data)
        video.embed_url = validator_resp.embed_url

        session.add(video)
        await session.commit()
        await session.refresh(video)

        return video

    @staticmethod
    async def delete_video(session: AsyncSession, id: str, current_user: Account):

        video = await session.get(VideoContent, id)

        if not video:
            raise HTTPException(404, "video content does not exist")

        await CourseService._run_module_checks(
            session, video.module_id, current_user.id, ModuleType.VIDEO
        )

        await session.delete(video)
        await session.commit()

    @staticmethod
    async def create_document(
        session: AsyncSession, data: DocumentContentCreate, current_user: Account
    ):

        await CourseService._run_module_checks(
            session, data.module_id, current_user.id, ModuleType.DOCUMENT
        )

        validator_resp = await CourseService._validate_document(
            data.file_url, data.platform
        )

        cleaned_data = data.model_dump(exclude_unset=True)
        doc = DocumentContent(**cleaned_data)
        doc.embed_url = validator_resp.embed_url
        doc.file_size_bytes = validator_resp.file_size

        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        return doc

    @staticmethod
    async def update_document(
        session: AsyncSession,
        id: str,
        data: DocumentContentUpdate,
        current_user: Account,
    ):

        doc = await session.get(DocumentContent, id)

        if not doc:
            raise HTTPException(404, "document does not exist")

        await CourseService._run_module_checks(
            session, doc.module_id, current_user.id, ModuleType.DOCUMENT
        )

        validator_resp = await CourseService._validate_document(
            data.file_url or doc.file_url, data.platform or doc.platform
        )

        cleaned_data = data.model_dump(exclude_unset=True)
        doc.sqlmodel_update(cleaned_data)
        doc.embed_url = validator_resp.embed_url
        doc.file_size_bytes = validator_resp.file_size

        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        return doc

    @staticmethod
    async def delete_document(session: AsyncSession, id: str, current_user: Account):

        doc = await session.get(DocumentContent, id)

        if not doc:
            raise HTTPException(404, "document does not exist")

        await CourseService._run_module_checks(
            session, doc.module_id, current_user.id, ModuleType.DOCUMENT
        )

        await session.delete(doc)
        await session.commit()

    @staticmethod
    async def add_course_attachments(
        session: AsyncSession,
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
        await session.commit()

    @staticmethod
    async def remove_course_attachments(
        session: AsyncSession,
        attachment_id: str,
        current_user: Account,
    ):

        attachment = await session.get(ModuleAttachment, attachment_id)
        if not attachment:
            raise HTTPException(404, "attachment does not exist")

        section = await session.get(Section, attachment.module.section_id)

        assert section is not None

        if section.course.account_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="permission denied"
            )

        await session.delete(attachment)
        await session.commit()

    @staticmethod
    async def get_enrollment(
        course_id: str, session: AsyncSession, curent_user: Account
    ):
        enrollment = (
            await session.exec(
                select(CourseEnrollment).where(
                    CourseEnrollment.course_id == course_id,
                    CourseEnrollment.account_id == curent_user.id,
                )
            )
        ).first()

        if not enrollment:
            raise HTTPException(404, "not enrolled")

        return enrollment

    @staticmethod
    async def get_progress(course_id: str, session: AsyncSession, curent_user: Account):
        progress = (
            await session.exec(
                select(CourseProgress).where(
                    CourseProgress.course_id == course_id,
                    CourseProgress.account_id == curent_user.id,
                )
            )
        ).first()

        if not progress:
            raise HTTPException(404, "no progress found")

        return progress

    @staticmethod
    async def create_enrollment(
        session: AsyncSession,
        data: CourseEnrollmentCreate,
        current_user: Account,
    ):

        course = await session.get(Course, data.course_id)

        # TODO: before enrollment check for criteria like pay for paid courses
        # -

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="course not found"
            )

        if course.enrollment_type == EnrollmentType.OPEN:
            return await CourseService._create_entollment(
                course, data, session, current_user
            )

    @staticmethod
    async def create_course_rating(
        session: AsyncSession,
        data: CourseRatingCreate,
        current_user: Account,
    ):
        course = await session.get(Course, data.course_id)
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="course not found"
            )

        enrollment = (
            await session.exec(
                select(CourseEnrollment).where(
                    CourseEnrollment.course_id == data.course_id,
                    CourseEnrollment.account_id == current_user.id,
                )
            )
        ).first()
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot rate a course you have not enrolled for",
            )

        # Check if user already rated this course
        existing_rating = (
            await session.exec(
                select(Rating).where(
                    Rating.course_id == data.course_id,
                    Rating.account_id == current_user.id,
                )
            )
        ).first()

        if existing_rating:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already rated this course",
            )

        try:

            # Create comment first
            comment = Comment(
                message=data.message,
                is_rating=True,
                course_id=data.course_id,
                creator_id=current_user.id,
            )
            session.add(comment)
            await session.flush()  # Get the comment ID without committing

            # Create rating
            cleaned_data = data.model_dump(exclude_unset=True)
            rating = Rating(**cleaned_data)
            rating.account_id = current_user.id
            rating.comment_id = comment.id
            session.add(rating)
            await session.flush()  # Ensure rating is created

            # Atomically update course statistics using SQLModel's update
            update_stmt = (
                update(Course)
                .where(cast(BinaryExpression, Course.id == data.course_id))
                .values(
                    total_rating=func.coalesce(Course.total_rating, 0) + 1,
                    stars=func.coalesce(Course.stars, 0) + data.star,
                    average_rating=(func.coalesce(Course.stars, 0) + data.star)
                    / (func.coalesce(Course.total_rating, 0) + 1),
                )
            )

            await session.exec(update_stmt)  # type: ignore
            await session.commit()

            # Refresh to get updated values
            await session.refresh(rating)
            await session.refresh(course)

            return rating

        except Exception as e:
            await session.rollback()
            raise e

    @staticmethod
    async def list_ratings(
        course_id: str, session: AsyncSession, page: int = 1, per_page: int = PER_PAGE
    ):

        query = select(Rating).join(Comment).where(Rating.course_id == course_id)

        return await paginate(session, query, page, per_page)

    @staticmethod
    async def create_comment(
        session: AsyncSession,
        data: CourseCommentCreate,
        current_user: Account,
    ):
        course = await session.get(Course, data.course_id)

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="course not found"
            )

        comment_replied = None

        if data.reply_to_id:
            comment_replied = await session.get(Comment, data.reply_to_id)

            if not comment_replied:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="comment not found"
                )

        try:

            if not data.reply_to_id:
                comment = Comment(**data.model_dump(exclude_unset=True))
                comment.is_rating = False
                comment.creator_id = current_user.id
                session.add(comment)
                await session.flush()
            elif comment_replied:

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
                session.add(comment)
                await session.flush()

                # comment_count increment
                upgraded_parent = await session.get(Comment, reply_to_id)
                assert upgraded_parent is not None

                update_stmt_parent = (
                    update(Comment)
                    .where(cast(BinaryExpression, Comment.id == reply_to_id))
                    .values(
                        comment_count=func.coalesce(Comment.comment_count, 0) + 1,
                    )
                )

                await session.exec(update_stmt_parent)  # type: ignore
            # increment course comment count
            # Atomically update course statistics using SQLModel's update
            update_stmt = (
                update(Course)
                .where(cast(BinaryExpression, Course.id == data.course_id))
                .values(
                    comment_count=func.coalesce(Course.comment_count, 0) + 1,
                )
            )

            await session.exec(update_stmt)  # type: ignore
            await session.commit()
            await session.refresh(comment)
            return comment
        except Exception as e:
            await session.rollback()
            raise e

    @staticmethod
    async def update_comment(
        session: AsyncSession,
        id: str,
        data: CourseCommentUpdate,
        current_user: Account,
    ):
        comment = await session.get(Comment, id)

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
            rating = (
                await session.exec(
                    select(Rating).where(Rating.comment_id == comment.id)
                )
            ).first()
            if rating:
                rating.message = message
                session.add(rating)

        session.add(comment)
        await session.commit()
        await session.refresh(comment)
        return comment

    @staticmethod
    async def list_comments(
        course_id: str,
        session: AsyncSession,
        page: int = 1,
        current_user: Optional[Account] = None,
        per_page: int = PER_PAGE,
    ):
        query = (
            select(Comment)
            .where(
                Comment.course_id == course_id,
                Comment.is_rating == False,
                Comment.reply_to == None,
            )
            .order_by(desc(Comment.created_at))
        )

        data = await paginate(session, query, page, per_page)

        if current_user:
            likes = (
                await session.exec(
                    select(CommentLike, Comment.course_id)
                    .join(CommentLike)
                    .where(
                        Comment.course_id == course_id,
                        CommentLike.account_id == current_user.id,
                    )
                )
            ).all()

            like_map = {}
            for comment_like, _ in likes:
                like_map[comment_like.comment_id] = True

            def _fill(x: Comment):
                comment_read = CourseCommentRead.model_validate(x)
                return comment_read.model_copy(
                    update={"is_liked": like_map.get(x.id, False)}
                )

            data["items"] = list(map(_fill, data["items"]))

        return data

    @staticmethod
    async def list_replies(
        comment_id: str,
        session: AsyncSession,
        page: int = 1,
        current_user: Optional[Account] = None,
        per_page: int = PER_PAGE,
    ):
        query = (
            select(Comment)
            .where(Comment.reply_to_id == comment_id)
            .order_by(desc(Comment.created_at))
        )

        data = await paginate(session, query, page, per_page)

        if current_user:
            likes = (
                await session.exec(
                    select(CommentLike, Comment)
                    .join(CommentLike)
                    .where(
                        Comment.reply_to_id == comment_id,
                        CommentLike.account_id == current_user.id,
                    )
                )
            ).all()

            like_map = {}
            for comment_like, _ in likes:
                like_map[comment_like.comment_id] = True

            def _fill(x: Any):
                comment_read = CourseCommentRead.model_validate(x)
                return comment_read.model_copy(
                    update={"is_liked": like_map.get(x.id, False)}
                )

            data["items"] = list(map(_fill, data["items"]))

        return data

    @staticmethod
    async def like_unlike(
        comment_id: str, session: AsyncSession, current_user: Account
    ):

        comment = await session.get(Comment, comment_id)

        if not comment:
            raise HTTPException(404, "comment not found!")

        like = (
            await session.exec(
                select(CommentLike).where(
                    CommentLike.account_id == current_user.id,
                    CommentLike.comment_id == comment_id,
                )
            )
        ).first()

        if like:
            await session.delete(like)
            update_stmt = (
                update(Comment)
                .where(cast(BinaryExpression, Comment.id == comment_id))
                .values(
                    likes=func.coalesce(Comment.likes, 1) - 1,
                )
            )
            await session.exec(update_stmt)  # type:  ignore
        else:
            session.add(CommentLike(account_id=current_user.id, comment_id=comment.id))
            update_stmt = (
                update(Comment)
                .where(cast(BinaryExpression, Comment.id == comment_id))
                .values(
                    likes=func.coalesce(Comment.likes, 0) + 1,
                )
            )
            await session.exec(update_stmt)  # type:  ignore
        await session.commit()

        return

    @staticmethod
    async def add_tag_to_course():
        pass

    @staticmethod
    async def _run_module_checks(
        session: AsyncSession,
        module_id: uuid.UUID,
        user_id: uuid.UUID,
        module_type: ModuleType | None = None,
    ):
        results = (
            await session.exec(
                select(Module, Section).join(Section).where(Module.id == module_id)
            )
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
    async def _get_course_or_404(
        slug: str, session: AsyncSession, currentUser: Optional[Account] = None
    ):
        course = (await session.exec(select(Course).where(Course.slug == slug))).first()

        if not course:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "course not found")

        if currentUser and currentUser.id == course.account_id:
            return course
        if course.status.value == "draft" or course.status.value == "archived":
            raise HTTPException(status.HTTP_403_FORBIDDEN)

        return course

    @staticmethod
    async def _generate_course_slug(title: str, session: AsyncSession):
        counter = 0
        orignal_slug = slugify(title)
        slug = orignal_slug

        while bool(
            (await session.exec(select(Course).where(Course.slug == slug))).first()
        ):
            counter += 1
            slug = orignal_slug + f"-{counter}"

        return slug

    @staticmethod
    async def _create_entollment(
        course: Course,
        data: CourseEnrollmentCreate,
        session: AsyncSession,
        current_user: Account,
    ):
        try:

            cleaned_data = data.model_dump(exclude_unset=True)
            enrollment = CourseEnrollment(**cleaned_data)
            enrollment.account_id = current_user.id

            session.add(enrollment)
            await session.flush()

            progress = CourseProgress(
                account_id=current_user.id,
                course_id=course.id,
                start_time=datetime.now(timezone.utc),
                status=ModuleProgressStatus.IN_PROGRESS,
                last_active_date=datetime.now(timezone.utc),
            )

            session.add(progress)
            await session.flush()

            update_stmt = (
                update(Course)
                .where(cast(BinaryExpression, Course.id == data.course_id))
                .values(
                    enrollment_count=func.coalesce(Course.enrollment_count, 0) + 1,
                )
            )

            await session.exec(update_stmt)  # type: ignore

            await session.commit()
            await session.refresh(enrollment)
            return enrollment
        except Exception as e:
            await session.rollback()
            raise e

    @staticmethod
    async def _validate_video(video_url: str, platform: VideoPlatform):
        provider = DocumentPlatform.DROPBOX
        if platform == VideoPlatform.YOUTUBE or platform == VideoPlatform.DAILYMOTION:
            provider = DocumentPlatform.DIRECT_LINK
        elif platform == VideoPlatform.GOOGLE_DRIVE:
            provider = DocumentPlatform.GOOGLE_DRIVE

        validator_resp = await URLValidator.validate_url_resource(
            DocumentItem(
                url=HttpUrl(video_url),
                provider=provider,
                media_type=MediaType.VIDEO,
            )
        )

        if not validator_resp.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid video"
            )

        return validator_resp

    @staticmethod
    async def _validate_document(file_url: str, platform: DocumentPlatform):
        validator_resp = await URLValidator.validate_url_resource(
            DocumentItem(
                url=HttpUrl(file_url),
                provider=platform,
                media_type=MediaType.DOCUMENT,
            )
        )

        if not validator_resp.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid document"
            )

        return validator_resp

    @staticmethod
    async def _sync_course_tags(
        session: AsyncSession, course: Course, tag_names: list[str]
    ):
        """Create, reuse, or remove tags associated with a course."""
        # Normalize tag names
        new_tags = {t.strip().lower() for t in tag_names if t.strip()}
        current_tags = {t.name for t in course.tags}

        tags_to_add = new_tags - current_tags
        tags_to_remove = current_tags - new_tags

        # Remove old tags
        if tags_to_remove:
            for tag in list(course.tags):
                if tag.name in tags_to_remove:
                    tag.usage_count -= 1
                    if tag.usage_count <= 0:
                        await session.delete(tag)
                    else:
                        session.add(tag)
                    course.tags.remove(tag)

        # Add or reuse tags
        for name in tags_to_add:
            existing_tag = (
                await session.exec(select(Tag).where(Tag.name == name))
            ).first()
            if existing_tag:
                existing_tag.usage_count += 1
                course.tags.append(existing_tag)
            else:
                new_tag = Tag(name=name, usage_count=1)
                session.add(new_tag)
                course.tags.append(new_tag)

        session.add(course)
        await session.commit()
        await session.refresh(course)
