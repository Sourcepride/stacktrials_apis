import uuid
from datetime import datetime, timezone
from typing import Optional, cast

from sqlalchemy import BinaryExpression
from sqlmodel import desc, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.common.constants import PER_PAGE
from app.common.utils import CursorPaginationSerializer, notification_ws_channel
from app.common.ws_manager import manager
from app.models.notification_model import Notification
from app.models.user_model import Account
from app.schemas.notification import NotificationWrite


class NotificationService:
    @staticmethod
    async def create_notification(
        session: AsyncSession, current_user: Account, data: NotificationWrite
    ):

        cleaned_data = data.model_dump()
        notification = Notification(**cleaned_data)
        notification.account_id = current_user.id

        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        key = notification_ws_channel(current_user)
        await manager.publish(
            key,
            {"event": "notification.create", "data": notification.model_dump_json()},
        )

        return notification

    @staticmethod
    async def list_notifications(
        session: AsyncSession,
        current_user: Account,
        last_message_id: Optional[str] = None,
        cursor_type: Optional[str] = None,
        limit: int = PER_PAGE,
    ):

        query = select(Notification).where(Notification.account_id == current_user.id)

        if last_message_id:
            last_message = (
                await session.exec(
                    select(Notification).where(
                        Notification.id == last_message_id,
                        Notification.account_id == current_user.id,
                    )
                )
            ).first()

            if last_message and cursor_type == "before":
                query = query.where(Notification.created_at < last_message.created_at)
            elif last_message and cursor_type == "after":
                query = query.where(Notification.created_at > last_message.created_at)

        query = query.order_by(desc(Notification.created_at)).limit(limit)
        messages = (await session.exec(query)).all()
        hasNext = bool(
            (
                await session.exec(
                    select(Notification).where(
                        Notification.created_at < messages[-1].created_at
                    )
                )
            ).first()
        )
        return CursorPaginationSerializer(
            messages, messages[-1].id, messages[0].id, hasNext
        )

    @staticmethod
    async def mark_read(
        session: AsyncSession, notification_id: str, account_id: uuid.UUID
    ):
        notification = await session.get(Notification, notification_id)
        if not notification or notification.account_id != account_id:
            return None

        notification.is_read = True
        notification.read_at = datetime.now(tz=timezone.utc)

        session.add(notification)
        await session.commit()
        return notification

    @staticmethod
    async def mark_all_read(session: AsyncSession, current_user: Account):
        now = datetime.now(tz=timezone.utc)

        stmt = (
            update(Notification)
            .where(
                cast(BinaryExpression, Notification.account_id == current_user.id),
                cast(BinaryExpression, Notification.is_read == False),
            )
            .values(
                is_read=True,
                read_at=now,
                updated_at=now,  # inherited from AppBaseModelMixin
            )
        )

        result = await session.exec(stmt)
        await session.commit()

        return result.rowcount or 0
