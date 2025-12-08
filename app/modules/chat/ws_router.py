import asyncio
import traceback
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException

from app.common.constants import PER_PAGE
from app.common.utils import chat_history_ws_channel, websocket_error_wrapper
from app.common.ws_manager import manager
from app.core.dependencies import CurrentWSUser, SessionDep
from app.modules.chat.service import ChatService
from app.schemas.chat import (
    ChatMessageRead,
    ChatMessageUpdate,
    ChatMessageWrite,
    ChatRead,
    PaginatedMessages,
)

if TYPE_CHECKING:
    from app.common.ws_manager import LocalConnection

router = APIRouter()


@router.websocket("/")
async def connect_chat_histories(
    websocket: WebSocket,
    session: SessionDep,
    current_user: CurrentWSUser,
    q: Optional[str] = None,
    page: Optional[int] = None,
):
    await websocket.accept()
    initial_data = await ChatService.list_chat(
        session, current_user, page or 1, PER_PAGE, q
    )

    initial_data = [
        {
            **item,
            "chat": item["chat"].model_dump(mode="json"),
            "last_message": (
                item["last_message"].model_dump(mode="json")
                if item["last_message"]
                else None
            ),
        }
        for item in initial_data["items"]
    ]
    await websocket.send_json({"event": "chat.list", "data": initial_data})

    sub_key = chat_history_ws_channel(current_user)
    conns: dict[str, LocalConnection] = {}
    local_conn = await manager.subscribe_local(sub_key, websocket)
    conns[sub_key] = local_conn

    async def cleanup_all_connections():
        """Clean up all connections with timeout protection and parallel execution"""
        if not conns:
            return

        # Create cleanup tasks for all connections in parallel
        cleanup_tasks = []
        for key_, con in list(conns.items()):
            try:
                # Wrap each unsubscribe with a timeout
                task = asyncio.wait_for(
                    manager.unsubscribe_local(key_, con),
                    timeout=2.0,  # 2 second timeout per connection
                )
                cleanup_tasks.append(task)
            except Exception:
                pass  # If task creation fails, continue with others

        # Execute all cleanups in parallel with exception handling
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    try:
        while True:
            try:
                raw_data = await websocket.receive_json()
            except WebSocketDisconnect:
                # Re-raise disconnect to outer handler
                raise
            except Exception:
                # Only catch parsing/validation errors, not disconnects
                continue

            event = raw_data.get("event")
            data = raw_data.get("data")

            if event == "chat.subscribe":

                if not isinstance(data, str):
                    raise WebSocketException(1002, "data must be a chat_id in string")
                con = await manager.subscribe_local(data, websocket)
                conns[data] = con
            elif event == "chat.unsubscribe":
                if not isinstance(data, str):
                    raise WebSocketException(1002, "data must be a chat_id in string")
                await manager.unsubscribe_local(data, conns[data])
                conns.pop(data, None)  # Remove from tracking

    except WebSocketDisconnect:
        # Clean up all connections on disconnect
        await cleanup_all_connections()
    except Exception as exc:
        # logger.exception("Exception in websocket handler: %s", exc)
        # ensure cleanup on any other error
        await cleanup_all_connections()
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/{chat_id}")
async def connect_to_chat(
    websocket: WebSocket, chat_id: str, session: SessionDep, current_user: CurrentWSUser
):
    """
    user comes in
    we check if the chat id exists
    if yes we get if the the user is an active member of the chat
    if yes we then proceed to fetch the initial data that is page one data
    after which we open the websocket for the user
    """

    await websocket.accept()
    initial_data = await ChatService.get_initial_data(chat_id, session, current_user)

    await websocket.send_json(
        {
            "event": "chat.initial",
            "data": PaginatedMessages.model_validate(initial_data).model_dump(
                mode="json"
            ),
        }
    )

    local_conn = await manager.subscribe_local(chat_id, websocket)
    sync_key = chat_history_ws_channel(current_user)
    sync_conn = await manager.subscribe_local(sync_key, websocket)
    try:
        while True:
            try:
                raw_data = await websocket.receive_json()
            except WebSocketDisconnect:
                # Re-raise disconnect to outer handler
                raise
            except Exception:
                # Only catch parsing/validation errors, not disconnects
                continue

            event = raw_data.get("event")
            data = raw_data.get("data")

            if event == "chat.message.create":

                resp = await websocket_error_wrapper(
                    ChatService.create_message,
                    session,
                    current_user,
                    ChatMessageWrite.model_validate(data),
                )

                model = ChatMessageRead.model_validate(resp)

                await manager.publish(
                    chat_id,
                    {
                        "event": "chat.message.create",
                        "data": model.model_dump(mode="json"),
                    },
                )

            elif event == "chat.message.update":
                resp = await websocket_error_wrapper(
                    ChatService.update_message,
                    session,
                    current_user,
                    data.get("message_id"),
                    ChatMessageUpdate.model_validate(data, extra="ignore"),
                )
                model = ChatMessageRead.model_validate(resp)
                await manager.publish(
                    chat_id,
                    {
                        "event": "chat.message.update",
                        "data": model.model_dump(mode="json"),
                    },
                )
            elif event == "chat.message.delete":
                if not isinstance(data, str):
                    raise WebSocketException(1002, "data must be a string")
                resp = await websocket_error_wrapper(
                    ChatService.delete_message, session, current_user, data
                )
                model = ChatMessageRead.model_validate(resp)
                await manager.publish(
                    chat_id,
                    {
                        "event": "chat.message.delete",
                        "data": model.model_dump(mode="json"),
                    },
                )
            elif event == "chat.update":
                resp = await websocket_error_wrapper(
                    ChatService.update_chat, session, current_user, chat_id, data
                )
                model = ChatRead.model_validate(resp)
                await manager.publish(
                    chat_id,
                    {"event": "chat.update", "data": model.model_dump(mode="json")},
                )
                await manager.publish(
                    sync_key,
                    {"event": "chat.update", "data": model.model_dump(mode="json")},
                )
            elif event == "chat.reaction.create" or event == "chat.reaction.delete":
                message_id = raw_data.get("message_id")
                if not message_id:
                    raise WebSocketException(1002, "message_id must be present")

                resp = await websocket_error_wrapper(
                    ChatService.create_delete_reaction,
                    session,
                    current_user,
                    message_id,
                    data,
                )
                model = ChatMessageRead.model_validate(resp)
                await manager.publish(
                    chat_id,
                    {
                        "event": "chat.message.update",
                        "data": model.model_dump(mode="json"),
                    },
                )
            elif event == "chat.member.delete":
                if isinstance(data, str):
                    raise WebSocketException(1002, "data must be a string")
                resp = await websocket_error_wrapper(
                    ChatService.remove_member, session, current_user, chat_id, data
                )
                await manager.publish(
                    chat_id,
                    {"event": "chat.member.delete", "data": model.model_dump_json()},
                )
            # END OF EVENTS

            stat_resp = (
                {
                    "event": "chat.stat",
                    "data": {
                        **await ChatService.fetch_one_unread_stats(
                            session, chat_id, current_user.id
                        ),
                        "chat_id": chat_id,
                    },
                },
            )

            await manager.publish(chat_id, stat_resp)
            await manager.publish(sync_key, stat_resp)

    except WebSocketDisconnect:
        # Clean up with timeout protection
        try:
            await asyncio.wait_for(
                manager.unsubscribe_local(chat_id, local_conn), timeout=2.0
            )
        except Exception:
            pass  # Cleanup failed, but don't block
    except Exception as exc:
        # logger.exception("Exception in websocket handler: %s", exc)
        # ensure cleanup

        print("-- catch all error -----", exc)
        print(traceback.format_exc())
        try:
            await asyncio.wait_for(
                manager.unsubscribe_local(chat_id, local_conn), timeout=2.0
            )
        except Exception:
            pass  # Cleanup failed, but don't block
        try:
            await websocket.close()
        except Exception:
            pass
