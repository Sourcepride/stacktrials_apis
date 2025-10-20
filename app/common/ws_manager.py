import asyncio
from collections import defaultdict
from typing import DefaultDict, Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: DefaultDict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, doc_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active_connections[doc_id].add(ws)

    async def disconnect(self, doc_id: str, ws: WebSocket):
        async with self._lock:
            self.active_connections[doc_id].discard(ws)
            if not self.active_connections[doc_id]:
                del self.active_connections[doc_id]

    async def broadcast_local(self, doc_id: str, message: dict):
        """Broadcast message to all local clients connected to this doc."""
        conns = list(self.active_connections.get(doc_id, []))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(doc_id, ws)


manager = ConnectionManager()
