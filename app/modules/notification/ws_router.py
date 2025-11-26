from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.common.utils import notification_ws_channel
from app.common.ws_manager import manager
from app.core.dependencies import CurrentWSUser, SessionDep
from app.models.notification_model import Notification
from app.modules.notification.service import NotificationService

if TYPE_CHECKING:
    from app.common.ws_manager import LocalConnection

router = APIRouter()


@router.websocket("/")
async def connect_chat_histories(
    websocket: WebSocket, session: SessionDep, current_user: CurrentWSUser
):

    await websocket.accept()
    initial_data = await NotificationService.list_notifications(session, current_user)
    await websocket.send_json({"event": "notification.list", "data": initial_data})

    sub_key = notification_ws_channel(current_user)

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
