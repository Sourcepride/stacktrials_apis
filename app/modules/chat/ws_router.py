from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException

from app.common.constants import PER_PAGE
from app.common.utils import websocket_error_wrapper, ws_code_from_http_code
from app.common.ws_manager import manager
from app.core.dependencies import CurrentWSUser, SessionDep
from app.modules.chat.service import ChatService
from app.schemas.chat import ChatMessageRead, ChatRead

router = APIRouter()


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
    await websocket.send_json({"event": "chat.initial", "data": initial_data})

    local_conn = await manager.subscribe_local(chat_id, websocket)

    try:
        while True:
            try:
                raw_data = await websocket.receive_json()
            except Exception:
                continue

            event = raw_data.get("event")
            data = raw_data.get("data")

            if event == "chat.message.create":
                resp = await websocket_error_wrapper(
                    ChatService.create_message, session, current_user, data
                )
                model = ChatMessageRead.model_validate(resp)
                await manager.publish(
                    chat_id,
                    {"event": "chat.message.create", "data": model.model_dump()},
                )
            elif event == "chat.message.update":
                resp = await websocket_error_wrapper(
                    ChatService.update_chat, session, current_user, chat_id, data
                )
                model = ChatMessageRead.model_validate(resp)
                await manager.publish(
                    chat_id,
                    {"event": "chat.message.update", "data": model.model_dump()},
                )
            elif event == "chat.message.delete":
                if isinstance(data, str):
                    raise WebSocketException(1002, "data must be a string")
                resp = await websocket_error_wrapper(
                    ChatService.delete_message, session, current_user, data
                )
                model = ChatMessageRead.model_validate(resp)
                await manager.publish(
                    chat_id,
                    {"event": "chat.message.delete", "data": model.model_dump()},
                )
            elif event == "chat.update":
                resp = await websocket_error_wrapper(
                    ChatService.update_chat, session, current_user, chat_id, data
                )
                model = ChatRead.model_validate(resp)
                await manager.publish(
                    chat_id,
                    {"event": "chat.update", "data": model.model_dump()},
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
                    {"event": "chat.message.update", "data": model.model_dump()},
                )
            elif event == "chat.member.delete":
                if isinstance(data, str):
                    raise WebSocketException(1002, "data must be a string")
                resp = await websocket_error_wrapper(
                    ChatService.remove_member, session, current_user, chat_id, data
                )
                await manager.publish(
                    chat_id,
                    {"event": "chat.member.delete", "data": model.model_dump()},
                )

    except WebSocketDisconnect:
        await manager.unsubscribe_local(chat_id, local_conn)
    except Exception as exc:
        # logger.exception("Exception in websocket handler: %s", exc)
        # ensure cleanup
        await manager.unsubscribe_local(chat_id, local_conn)
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/chat")
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
    await websocket.send_json({"event": "chat.list", "data": initial_data})

    sub_key = f"personal_chat:{current_user.id}"

    local_conn = await manager.subscribe_local(sub_key, websocket)

    try:
        while True:
            try:
                raw_data = await websocket.receive_json()
            except Exception:
                continue

            event = raw_data.get("event")
            data = raw_data.get("data")

    except WebSocketDisconnect:
        await manager.unsubscribe_local(sub_key, local_conn)
    except Exception as exc:
        # logger.exception("Exception in websocket handler: %s", exc)
        # ensure cleanup
        await manager.unsubscribe_local(sub_key, local_conn)
        try:
            await websocket.close()
        except Exception:
            pass
