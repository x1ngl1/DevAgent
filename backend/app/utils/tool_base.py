"""Tool definition base class and schema"""
import json
from typing import Dict, Any, Optional, Callable, Awaitable, List


class ToolResult:
    def __init__(self, success: bool, data: Any = None, error: str = None, content_type: str = "text"):
        self.success = success
        self.data = data
        self.error = error
        self.content_type = content_type

    def to_dict(self) -> Dict:
        return {"success": self.success, "data": self.data, "error": self.error, "content_type": self.content_type}

    def __str__(self) -> str:
        if not self.success:
            return "[Error] " + str(self.error)
        if self.content_type == "json":
            return json.dumps(self.data, ensure_ascii=False, indent=2)
        return str(self.data)


class ToolDef:
    def __init__(self, name: str, description: str, parameters: Dict, execute: Callable, timeout: int = 30, category: str = "general"):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.execute = execute
        self.timeout = timeout
        self.category = category

    def to_openai_tool(self) -> Dict:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}

    async def run(self, args: Dict, context: Dict = None) -> ToolResult:
        try:
            return await self.execute(args, context or {})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ToolCallRecord:
    def __init__(self, tool_name: str, args: Dict, result: ToolResult, duration: float):
        self.tool_name = tool_name
        self.args = args
        self.result = result
        self.duration = duration

    def to_dict(self) -> Dict:
        return {"tool_name": self.tool_name, "args": self.args, "result": self.result.to_dict(), "duration": round(self.duration, 2), "success": self.result.success}