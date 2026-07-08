"""Stream output service - push LLM tokens to frontend in real-time"""
import asyncio
import logging
from typing import Optional, AsyncGenerator

logger = logging.getLogger(__name__)


class StreamService:
    def __init__(self):
        self._sse_callback: Optional[callable] = None

    def set_sse_callback(self, callback: Optional[callable]):
        self._sse_callback = callback

    async def push_token(self, worker_id: str, token: str, accumulated: str):
        if self._sse_callback:
            await self._sse_callback("stream_token", {
                "worker_id": worker_id, "token": token, "accumulated": accumulated,
            })

    async def stream_from_generator(self, worker_id: str, generator: AsyncGenerator[str, None], delimiter: str = "\n") -> str:
        full_content = ""
        buffer = ""
        async for chunk in generator:
            if not chunk:
                continue
            full_content += chunk
            buffer += chunk
            while delimiter in buffer:
                idx = buffer.index(delimiter)
                sentence = buffer[:idx + len(delimiter)]
                buffer = buffer[idx + len(delimiter):]
                await self.push_token(worker_id, sentence, full_content)
                await asyncio.sleep(0.05)
        if buffer.strip():
            await self.push_token(worker_id, buffer, full_content)
        return full_content

    async def push_final_message(self, worker_id: str, content: str, phase: str = "execution", **extra):
        if self._sse_callback:
            data = {"role": worker_id, "content": content, "phase": phase, **extra}
            await self._sse_callback("chat_message", data)