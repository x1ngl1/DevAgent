"""Agent base class - tool calling and streaming support"""
import json
import logging
from typing import Dict, Any, Optional, Callable, List, AsyncGenerator

from app.utils.llm_factory import LLMFactory
from app.utils.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentBase:
    # 每个角色的默认工具类别映射
    ROLE_TOOL_CATEGORIES = {
        "coder": ["file", "code", "search"],
        "pm": ["file", "search"],
        "tester": ["file", "code"],
        "leader": ["search", "api"],
    }

    def __init__(self, worker_id: str, config: Dict[str, Any]):
        self.worker_id = worker_id
        self.config = config
        self._status_callback: Optional[Callable] = None
        # 自动根据角色设置默认工具类别
        self.default_tool_categories = self.ROLE_TOOL_CATEGORIES.get(worker_id, [])

    def set_status_callback(self, callback: Callable):
        self._status_callback = callback

    async def _update_status(self, status: str, data: Optional[Dict] = None):
        if self._status_callback:
            payload = {"worker_id": self.worker_id, "status": status, **(data or {})}
            await self._status_callback(payload)

    async def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return await LLMFactory.chat(self.worker_id, self.config, prompt, system_prompt)

    async def chat_with_tools(
        self, prompt: str, system_prompt: Optional[str] = None,
        tool_categories: Optional[List[str]] = None, stream_callback: Optional[Callable] = None,
    ) -> str:
        categories = tool_categories if tool_categories is not None else self.default_tool_categories
        result, records = await LLMFactory.chat_with_tools(
            self.worker_id, self.config, prompt, system_prompt,
            tool_categories=categories, stream_callback=stream_callback)
        for record in records:
            await self._update_status("tool_call", {
                "tool": record.get("tool_name", ""),
                "round": record.get("round", 0),
                "arguments": str(record.get("arguments", ""))[:200],
            })
        return result

    def parse_json_response(self, response: str) -> Dict:
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            if len(lines) > 2:
                response = "\n".join(lines[1:-1])
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}, response: {response[:200]}")
            raise ValueError(f"Agent returned invalid format: {e}")

    async def execute(self, context: Dict) -> Dict:
        raise NotImplementedError