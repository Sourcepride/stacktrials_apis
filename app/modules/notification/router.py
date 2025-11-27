from typing import Annotated, Optional

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentActiveUser, SessionDep
from app.modules.notification.service import NotificationService

router = APIRouter()


@router.get("/")
async def list_notifications(
    session: SessionDep,
    current_user: CurrentActiveUser,
    before: Annotated[
        Optional[str],
        Query(description="before message_id sent| used for cursor pagination"),
    ] = None,
    after: Annotated[
        Optional[str],
        Query(
            description="paginated messages after message_id sent| used for cursor pagination"
        ),
    ] = None,
):
    type_ = "before" if before else "after" if after else None
    message_id = after or before
    return await NotificationService.list_notifications(
        session, current_user, message_id, type_
    )


@router.get("/mark-al")
async def mark_all(
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await NotificationService.mark_all_read(session, current_user)


@router.get("/mark-read/{nid}")
async def mark_as_read(nid: str, session: SessionDep, current_user: CurrentActiveUser):
    return await NotificationService.mark_read(session, nid, current_user.id)
