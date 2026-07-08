"""SSE (Server-Sent Events) real-time push"""
import asyncio
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sse", tags=["sse"])


class SSEManager:
    def __init__(self):
        self._clients: set = set()

    async def register(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._clients.add(queue)
        logger.info(f"SSE client connected, total: {len(self._clients)}")
        return queue

    def unregister(self, queue: asyncio.Queue):
        self._clients.discard(queue)
        logger.info(f"SSE client disconnected, total: {len(self._clients)}")

    async def broadcast(self, event_type: str, data: dict):
        message = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        dead_queues = set()
        for queue in self._clients:
            try:
                await queue.put(message)
            except Exception:
                dead_queues.add(queue)
        for q in dead_queues:
            self._clients.discard(q)


sse_manager = SSEManager()


@router.get("/events")
async def sse_events(request: Request):
    queue = await sse_manager.register()
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            yield f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield message
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'time': 'keepalive'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            sse_manager.unregister(queue)
    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})