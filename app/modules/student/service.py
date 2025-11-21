from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import asc, col, desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.common.constants import PER_PAGE
from app.common.enum import EnrollmentStatus
from app.common.utils import paginate
from app.models.annotation_model import DocumentAnnotation
from app.models.courses_model import (
    Course,
    CourseEnrollment,
    CourseProgress,
    Module,
    Section,
)
from app.models.user_model import Account
from app.schemas.courses import LearnerStat


class StudentService:
    @staticmethod
    async def dashboard_stats(current_user: Account, session: AsyncSession):
        total_completed = (
            await session.exec(
                select(func.count(col(CourseEnrollment.id))).where(
                    CourseEnrollment.account_id == current_user.id,
                    CourseEnrollment.completion_date != None,
                )
            )
        ).one()
        in_progress = (
            await session.exec(
                select(func.count(col(CourseEnrollment.id))).where(
                    CourseEnrollment.account_id == current_user.id,
                    CourseEnrollment.completion_date == None,
                )
            )
        ).one()
        created_courses = (
            await session.exec(
                select(func.count(col(Course.id))).where(
                    Course.account_id == current_user.id
                )
            )
        ).one()

        return LearnerStat(
            completed_courses=total_completed,
            created_courses=created_courses,
            in_progress=in_progress,
        )

    @staticmethod
    async def enrolled(
        current_user: Account,
        session: AsyncSession,
        page: int = 1,
        per_page: int = PER_PAGE,
    ):
        enrolled = (
            select(Course, CourseEnrollment)
            .join(CourseEnrollment)
            .where(CourseEnrollment.account_id == current_user.id)
            .order_by(desc(CourseEnrollment.enrollment_date))
        )

        results = await paginate(session, enrolled, page, per_page)

        items: list[tuple[Course, CourseEnrollment]] = list(results.get("items", []))

        new_items = map(lambda x: {"course": x[0], "enrollment": x[1]}, items)

        results["items"] = list(new_items)

        return results

    @staticmethod
    async def save_video_progress():
        pass

    @staticmethod
    async def get_annotations(
        doc_id: str, current_user: Account, session: AsyncSession
    ):
        return (
            await session.exec(
                select(DocumentAnnotation).where(
                    DocumentAnnotation.account_id == current_user.id,
                    DocumentAnnotation.document_id == doc_id,
                )
            )
        ).all()

    @staticmethod
    async def toggle_module_completion_status(
        current_user: Account,
        session: AsyncSession,
        module_id: str,
        status: bool = True,
    ):
        resp = await StudentService._toggle_module_status(
            current_user, session, module_id, status
        )

        await session.commit()

        await session.refresh(resp[0])

        return resp[0]

    @staticmethod
    async def increment_progress(
        current_user: Account, session: AsyncSession, module_id: str
    ):
        module = (
            await session.exec(select(Module).where(Module.id == module_id))
        ).first()

        if not module:
            raise HTTPException(404, "module not found")

        progress = (
            await session.exec(
                select(CourseProgress).where(
                    CourseProgress.account_id == current_user.id,
                    CourseProgress.course_id == module.section.course_id,
                )
            )
        ).first()

        if not progress:
            raise HTTPException(404, "progress not found make sure you have enrolled")

        enrollment = (
            await session.exec(
                select(CourseEnrollment).where(
                    CourseEnrollment.account_id == current_user.id,
                    CourseEnrollment.course_id == module.section.course_id,
                )
            )
        ).first()

        if not enrollment:
            raise HTTPException(404, "enrollment not found")

        last_section = (
            await session.exec(
                select(Section)
                .where(Section.course_id == module.section.course_id)
                .order_by(desc(Section.order_index))
            )
        ).first()

        if not last_section:
            raise HTTPException(404, "last section not found")

        last_module = (
            await session.exec(
                select(Module)
                .where(Module.section_id == last_section.id)
                .order_by(desc(Module.order_index))
            )
        ).first()

        if not last_module:
            raise HTTPException(404, "last module not found")

        now = datetime.now(tz=timezone.utc)

        updates: dict[str, Any] = {"last_active_date": now}
        enrollment.last_accessed = now

        if last_module and last_module.order_index != module.order_index:
            next_module = (
                await session.exec(
                    select(Module)
                    .where(
                        Module.section_id == module.section_id,
                        Module.order_index > module.order_index,
                    )
                    .order_by(asc(Module.order_index))
                )
            ).first()

            if next_module:
                updates["next_module"] = next_module.id
                updates["next_section"] = next_module.section_id
            else:
                next_section = (
                    await session.exec(
                        select(Section)
                        .where(
                            Section.course_id == module.section.course_id,
                            Section.order_index > module.section.order_index,
                        )
                        .order_by(asc(Section.order_index))
                    )
                ).first()

                if not next_section:
                    raise ValueError("can not find next_module")

                updates["next_module"] = sorted(
                    next_section.modules, key=lambda x: x.order_index
                )[0].id
                updates["next_section"] = next_section.id

        if not progress.last_active_date:
            updates["current_streak"] = 1
            updates["longest_streak"] = 1
        else:
            hours_diff = (now - progress.last_active_date).total_seconds() / 3600
            if hours_diff <= 24:
                updates["current_streak"] = progress.current_streak
            elif hours_diff <= 49:
                updates["current_streak"] = progress.current_streak + 1
            else:
                updates["current_streak"] = 1
            updates["longest_streak"] = max(
                updates["current_streak"], progress.longest_streak
            )

        _, progress = await StudentService._toggle_module_status(
            current_user, session, module_id
        )
        progress.sqlmodel_update(updates)

        session.add(progress)
        await session.commit()
        await session.refresh(progress)

        return progress

    @staticmethod
    async def get_progress(
        current_user: Account, session: AsyncSession, course_id: str
    ):
        progress = (
            await session.exec(
                select(CourseProgress).where(
                    CourseProgress.account_id == current_user.id,
                    CourseProgress.course_id == course_id,
                )
            )
        ).first()

        if not progress:
            raise HTTPException(404, "progress not found")

        return progress

    @staticmethod
    async def _toggle_module_status(
        current_user: Account,
        session: AsyncSession,
        module_id: str,
        status: bool = True,
    ):

        module = (
            await session.exec(select(Module).where(Module.id == module_id))
        ).first()
        if not module:
            raise HTTPException(404, "Module not found")

        progress = (
            await session.exec(
                select(CourseProgress).where(
                    CourseProgress.account_id == current_user.id,
                    CourseProgress.course_id == module.section.course_id,
                )
            )
        ).first()

        if not progress:
            raise HTTPException(404, "Progress not found. Make sure you have enrolled.")

        enrollment = (
            await session.exec(
                select(CourseEnrollment).where(
                    CourseEnrollment.account_id == current_user.id,
                    CourseEnrollment.course_id == module.section.course_id,
                )
            )
        ).first()

        if not enrollment:
            raise HTTPException(404, "no enrollment found")

        progress_data = progress.progress_data or {"finished_modules": []}
        finished = set(progress_data.get("finished_modules", []))

        if not isinstance(finished, (list, set)):
            raise ValueError("Progress data for finished modules must be a list or set")

        if status:
            finished.add(module_id)
        else:
            finished.discard(module_id)

        all_modules = (
            await session.exec(
                select(Module)
                .join(Section)
                .where(Section.course_id == module.section.course_id)
            )
        ).all()

        total_modules = len(all_modules)
        completed_modules = len(finished)

        if completed_modules == total_modules and total_modules > 0:
            now = datetime.now(tz=timezone.utc)
            progress.completion_time = now
            enrollment.status = EnrollmentStatus.COMPLETED
            enrollment.completion_date = now
            enrollment.progress_percentage = 100
        else:
            enrollment.progress_percentage = (
                (completed_modules / total_modules) * 100 if total_modules else 0
            )

        progress.progress_data = {
            **progress_data,
            "finished_modules": list(finished),
        }

        session.add(progress)
        session.add(enrollment)
        return (enrollment, progress)
