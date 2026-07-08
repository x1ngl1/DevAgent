"""应用配置"""
import os
from dotenv import load_dotenv

load_dotenv()

# 服务配置
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# DeepSeek默认配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# Docker沙箱
SANDBOX_PYTHON_IMAGE = os.getenv("SANDBOX_PYTHON_IMAGE", "ai-sandbox-python:latest")

# 数据库
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")

# 默认Worker配置
DEFAULT_WORKER_CONFIG = {
    "provider": "aliyun",
    "model_name": "qwen-plus",
    "api_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "temperature": 0.3,
    "max_tokens": 4096,
    "timeout": 180,
}

WORKER_ROLES = {
    "leader": {"label": "Leader", "icon": "L", "description": "coordinator"},
    "coder": {"label": "Programmer", "icon": "C", "description": "code writing"},
    "pm": {"label": "PM Agent", "icon": "PM", "description": "quality review"},
    "tester": {"label": "Tester", "icon": "T", "description": "unit test"},
}

# ===== enhanced config =====
PARALLEL_MAX_WORKERS = int(os.getenv("PARALLEL_MAX_WORKERS", "4"))
STREAM_OUTPUT = os.getenv("STREAM_OUTPUT", "true") == "true"
INTERVENTION_MODE = os.getenv("INTERVENTION_MODE", "auto")
TOOL_TIMEOUT = int(os.getenv("TOOL_TIMEOUT", "30"))
CHECKPOINT_ENABLED = os.getenv("CHECKPOINT_ENABLED", "true") == "true"

SSE_EVENT_TASK_UPDATE = "task_update"
SSE_EVENT_SUBTASK_UPDATE = "subtask_update"
SSE_EVENT_WORKER_STATUS = "worker_status"
SSE_EVENT_CHAT_MESSAGE = "chat_message"
SSE_EVENT_STREAM_TOKEN = "stream_token"
SSE_EVENT_INTERVENTION_REQUEST = "intervention_request"
SSE_EVENT_TOOL_CALL_PROGRESS = "tool_call_progress"
SSE_EVENT_CHECKPOINT_REACHED = "checkpoint_reached"
SSE_EVENT_PAUSE_STATE = "pause_state"
SSE_EVENT_ERROR = "error"

TOOL_WEB_SEARCH_ENABLED = os.getenv("TOOL_WEB_SEARCH_ENABLED", "true") == "true"
TOOL_HTTP_REQUESTS_ENABLED = os.getenv("TOOL_HTTP_REQUESTS_ENABLED", "true") == "true"
TOOL_CODE_EXECUTION_ENABLED = os.getenv("TOOL_CODE_EXECUTION_ENABLED", "true") == "true"