import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from app.common.redis_client import get_redis
from app.common.ws_manager import manager
from app.core.dependencies import CurrentActiveUser, CurrentWSUser, SessionDep
from app.models.annotation_model import DocumentAnnotation

router = APIRouter()


def doc_channel(doc_id: str):
    return f"document:{doc_id}:annotations"


@router.websocket("/ws/documents/{doc_id}/annotations")
async def annotation_ws(
    websocket: WebSocket,
    doc_id: str,
    session: SessionDep,
    current_user: CurrentWSUser,
):
    """WebSocket endpoint for live document annotation sync."""
    await manager.connect(doc_id, websocket)
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(doc_channel(doc_id))

    # Background task to read Redis messages and forward to local clients
    async def redis_listener():
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1
                )
                if not msg:
                    await asyncio.sleep(0.05)
                    continue
                data = msg["data"]
                if isinstance(data, (bytes, bytearray)):
                    text = data.decode()
                else:
                    text = str(data)
                try:
                    payload = json.loads(text)
                except Exception:
                    payload = {"event": "raw", "data": text}
                await manager.broadcast_local(doc_id, payload)
        finally:
            await pubsub.unsubscribe(doc_channel(doc_id))

    listener_task = asyncio.create_task(redis_listener())

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")
            data = msg.get("data")

            # Handle annotation creation/update/delete
            if event == "annotation.create":
                ann = DocumentAnnotation(**data)
                ann.account_id = current_user.id
                ann.document_id = UUID(doc_id)
                session.add(ann)
                session.commit()
                session.refresh(ann)

                payload = {
                    "event": "annotation.created",
                    "data": {
                        "id": str(ann.id),
                        "type": ann.type,
                        "page_number": ann.page_number,
                        "content": ann.content,
                        "meta_data": ann.meta_data,
                        "account_id": str(current_user.id),
                    },
                }

                # Publish to Redis (all instances get this)
                await redis.publish(doc_channel(doc_id), json.dumps(payload))

            elif event == "annotation.delete":
                ann_id = data.get("id")
                ann = session.get(DocumentAnnotation, ann_id)

                if ann:
                    session.delete(ann)
                    session.commit()
                    payload = {
                        "event": "annotation.deleted",
                        "data": {"id": ann_id, "type": ann.type},
                    }
                    await redis.publish(doc_channel(doc_id), json.dumps(payload))

            elif event == "annotation.update":
                UPDATABLE_ANNOTATION_FIELDS = {
                    "content",
                    "page_number",
                    "meta_data",
                    "type",
                }
                ann_id = data.get("id")
                ann = session.get(DocumentAnnotation, ann_id)

                if ann:
                    for k, v in data.items():
                        if k in UPDATABLE_ANNOTATION_FIELDS:
                            setattr(ann, k, v)
                        else:
                            print(f"[Warning] Skipping non-updatable attribute: {k}")

                    session.add(ann)
                    session.commit()
                    session.refresh(ann)
                    payload = {
                        "event": "annotation.updated",
                        "data": {
                            "id": str(ann.id),
                            "type": ann.type,
                            "page_number": ann.page_number,
                            "content": ann.content,
                            "meta_data": ann.meta_data,
                            "account_id": str(current_user.id),
                        },
                    }
                    await redis.publish(doc_channel(doc_id), json.dumps(payload))

    except WebSocketDisconnect:
        await manager.disconnect(doc_id, websocket)
    finally:
        listener_task.cancel()
