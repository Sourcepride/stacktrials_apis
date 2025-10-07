from typing import Optional

from sqlmodel import Session, col, func, select

from app.common.constants import PER_PAGE
from app.common.enum import CourseStatus
from app.common.utils import paginate
from app.models.courses_model import Course
from app.models.user_model import Account
from app.schemas.courses import CreatorStat


class CreatorService:
    @staticmethod
    async def course_stat(current_user: Account, session: Session):
        total_enrolled = (
            session.exec(
                select(func.sum(Course.enrollment_count)).where(
                    Course.account_id == current_user.id
                )
            ).one_or_none()
            or 0
        )
        total_reviews = (
            session.exec(
                select(func.sum(Course.total_rating)).where(
                    Course.account_id == current_user.id
                )
            ).one_or_none()
            or 0
        )
        total_comments = (
            session.exec(
                select(func.sum(Course.comment_count)).where(
                    Course.account_id == current_user.id
                )
            ).one_or_none()
            or 0
        )
        average_rating = session.exec(
            select(func.avg(Course.average_rating)).where(
                Course.account_id == current_user.id
            )
        ).one_or_none()

        total_published = (
            session.exec(
                select(func.count(col(Course.id))).where(
                    Course.status == CourseStatus.PUBLISHED,
                    Course.account_id == current_user.id,
                )
            ).one_or_none()
            or 0
        )

        print("____________________", average_rating)

        return CreatorStat(
            total_comments=total_comments,
            total_enrolled=total_enrolled,
            total_reviews=total_reviews,
            total_published=total_published,
        )

    @staticmethod
    async def created_videos(
        title: Optional[str],
        current_user: Account,
        session: Session,
        page: int = 1,
        per_page: int = PER_PAGE,
    ):
        query = select(Course).where(Course.account_id == current_user.id)
        if title:
            query = query.where(col(Course.title).ilike(f"%{title}%"))

        return paginate(session, query, page, per_page)
