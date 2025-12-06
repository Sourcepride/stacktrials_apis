import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Query

from app.common.constants import PER_PAGE
from app.common.utils import chat_history_ws_channel
from app.common.ws_manager import manager
from app.core.dependencies import CurrentActiveUser, SessionDep
from app.modules.chat.service import ChatService
from app.schemas.base import OkModel
from app.schemas.chat import (
    ChatInviteBulkWrite,
    ChatInviteEmailWrite,
    ChatInviteRead,
    ChatInviteWrite,
    ChatMemberRead,
    ChatRead,
    ChatWrite,
    PaginatedChatInviteRead,
    PaginatedChatMemberRead,
    PaginatedChatRead,
    PaginatedChatReadWithUnReadCount,
    PaginatedMessages,
)

router = APIRouter()


@router.post("/", response_model=ChatRead)
async def create_chat(
    session: SessionDep,
    current_user: CurrentActiveUser,
    data: Annotated[ChatWrite, Body()],
):

    resp = await ChatService.create_chat(session, current_user, data)
    sub_key = chat_history_ws_channel(current_user)
    await manager.publish(sub_key, {"event": "chat.create", "data": resp.model_dump()})
    return resp


@router.get("/", response_model=PaginatedChatReadWithUnReadCount)
async def list_chats(
    session: SessionDep,
    current_user: CurrentActiveUser,
    page: int = 1,
    q: Optional[str] = None,
):
    return await ChatService.list_chat(session, current_user, page, PER_PAGE, q)


@router.get("/public/all", response_model=PaginatedChatRead)
async def list_public_chats(
    session: SessionDep, current_user: CurrentActiveUser, q: Optional[str] = None
):
    return await ChatService.list_all_public_chat(q, session, current_user)


@router.post("/invite", response_model=OkModel)
async def create_invite(
    session: SessionDep,
    current_user: CurrentActiveUser,
    bgTask: BackgroundTasks,
    data: Annotated[ChatInviteBulkWrite, Body()],
):
    return await ChatService.create_invite(session, current_user, bgTask, data)


@router.post("/invite/email", response_model=ChatInviteRead)
async def create_invite_by_email(
    session: SessionDep,
    current_user: CurrentActiveUser,
    bgTask: BackgroundTasks,
    data: Annotated[ChatInviteEmailWrite, Body()],
):
    return await ChatService.create_invite_by_email(session, current_user, bgTask, data)


@router.patch("/invite/accept/{token}", response_model=ChatMemberRead)
async def accept_invite(
    token: str, session: SessionDep, current_user: CurrentActiveUser
):
    resp = await ChatService.accept_invite(session, current_user, token)
    sub_key = chat_history_ws_channel(current_user)
    await manager.publish(sub_key, {"event": "chat.accept", "data": resp.model_dump()})
    return resp


@router.patch("/{chat_id}/join", response_model=ChatMemberRead)
async def join_public_chat(
    chat_id: str, session: SessionDep, current_user: CurrentActiveUser
):
    resp = await ChatService.join_public_group(
        session, uuid.UUID(chat_id), current_user
    )
    sub_key = chat_history_ws_channel(current_user)
    await manager.publish(
        sub_key, {"event": "chat.join_public", "data": resp.model_dump()}
    )
    return resp


@router.get("/{chat_id}/messages", response_model=PaginatedMessages)
async def list_messages(
    chat_id: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
    q: Optional[str] = None,
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
    return await ChatService.list_messages(
        chat_id, session, current_user, q, message_id, type_
    )


@router.get("/{chat_id}/members", response_model=PaginatedChatMemberRead)
async def list_members(
    chat_id: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
    page: int = 1,
):
    return await ChatService.list_members(session, current_user, chat_id, page)


@router.patch("/{chat_id}/make-admin/{member_id}", response_model=ChatMemberRead)
async def make_admin(
    chat_id: str, session: SessionDep, current_user: CurrentActiveUser, member_id: str
):
    return await ChatService.make_admin(session, current_user, chat_id, member_id)


@router.patch("/{chat_id}/remove-admin/{member_id}", response_model=ChatMemberRead)
async def remove_admin(
    chat_id: str, session: SessionDep, current_user: CurrentActiveUser, member_id: str
):
    return await ChatService.remove_admin(session, current_user, chat_id, member_id)


@router.patch("/{course_id}/add-directly/{user_id}", response_model=ChatRead)
async def add_directly(
    course_id: str, user_id: str, session: SessionDep, current_user: CurrentActiveUser
):
    resp = await ChatService.add_directly(session, current_user, user_id, course_id)
    sub_key = chat_history_ws_channel(current_user)
    await manager.publish(
        sub_key, {"event": "chat.direct.add", "data": resp.model_dump()}
    )
    return resp
