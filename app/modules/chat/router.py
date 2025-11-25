import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Query

from app.common.utils import chat_history_ws_channel
from app.common.ws_manager import manager
from app.core.dependencies import CurrentActiveUser, SessionDep
from app.models.chat_model import Chat
from app.modules.chat.service import ChatService
from app.schemas.chat import ChatInviteWrite, ChatWrite

router = APIRouter()


@router.post("/")
async def create_chat(
    session: SessionDep,
    current_user: CurrentActiveUser,
    data: Annotated[ChatWrite, Body()],
):

    resp = await ChatService.create_chat(session, current_user, data)
    sub_key = chat_history_ws_channel(current_user)
    await manager.publish(sub_key, {"type": "chat.create", "data": resp})
    return resp


@router.get("/public/all")
async def list_public_chats(
    session: SessionDep, current_user: CurrentActiveUser, q: Optional[str] = None
):
    return await ChatService.list_all_public_chat(q, session, current_user)


@router.post("/invite")
async def create_invite(
    session: SessionDep,
    current_user: CurrentActiveUser,
    bgTask: BackgroundTasks,
    data: ChatInviteWrite,
):
    return await ChatService.create_invite(session, current_user, bgTask, data)


@router.patch("/invite/accept/{token}")
async def accept_invite(
    token: str, session: SessionDep, current_user: CurrentActiveUser
):
    resp = await ChatService.accept_invite(session, current_user, token)
    sub_key = chat_history_ws_channel(current_user)
    await manager.publish(sub_key, {"type": "chat.accept", "data": resp})
    return resp


@router.patch("/{chat_id}/join")
async def join_public_chat(
    chat_id: str, session: SessionDep, current_user: CurrentActiveUser
):
    resp = await ChatService.join_public_group(
        session, uuid.UUID(chat_id), current_user
    )
    sub_key = chat_history_ws_channel(current_user)
    await manager.publish(sub_key, {"type": "chat.join_public", "data": resp})
    return resp


@router.get("/{chat_id}/messages")
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


@router.patch("/{chat_id}/make-admin/{member_id}")
async def make_admin(
    chat_id: str, session: SessionDep, current_user: CurrentActiveUser, member_id: str
):
    return await ChatService.make_admin(session, current_user, chat_id, member_id)


@router.patch("/{chat_id}/remove-admin/{member_id}")
async def remove_admin(
    chat_id: str, session: SessionDep, current_user: CurrentActiveUser, member_id: str
):
    return await ChatService.remove_admin(session, current_user, chat_id, member_id)


@router.patch("/{course_id}/add-directly/{user_id}")
async def add_directly(
    course_id: str, user_id: str, session: SessionDep, current_user: CurrentActiveUser
):
    resp = await ChatService.add_directly(session, current_user, user_id, course_id)
    sub_key = chat_history_ws_channel(current_user)
    await manager.publish(sub_key, {"type": "chat.direct.add", "data": resp})
    return resp
