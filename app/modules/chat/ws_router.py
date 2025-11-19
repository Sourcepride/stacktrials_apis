from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.common.ws_manager import LocalConnection
from app.core.dependencies import CurrentWSUser, SessionDep
from app.main import manager
from app.modules.chat.service import ChatService

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

            if event == "chat.create.message":
                pass
            elif event == "chat.update.message":
                pass
            elif event == "chat.delete.message":
                pass
            elif event == "chat.update":
                pass
            elif event == "chat.create.reaction":
                pass
            elif event == "chat.delete.reaction":
                pass
            elif event == "chat.member.delete":
                pass

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
