"""简单对话API — 自动识别简单问答 vs 编程任务"""
import json
import logging
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils.llm_factory import LLMFactory
from app.services.worker_config_service import WorkerConfigService
from app.utils.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    user_input: str


CLASSIFY_SYSTEM_PROMPT = """你是一个智能助手，负责判断用户的问题是"简单问答"还是"编程任务"。

## 简单问答（回复 "direct"）
- 询问时间、日期、天气
- 常识性问题、定义解释
- 闲聊、打招呼
- 翻译、润色文字
- 数学计算
- 不需要写代码、创建文件的一般性问题

## 编程任务（回复 "task"）
- 要求写代码、创建项目、开发功能
- 要求写网页、App、脚本程序
- 要求测试代码、审查代码
- 需要多步骤执行的开发任务

请只回复以下格式的 JSON（不要有多余文字）：
{"type": "direct"} 或 {"type": "task"}"""

DIRECT_ANSWER_SYSTEM = """你是 AI 开发团队的智能助手，请直接回答用户的问题。

**重要规则：如果用户询问实时信息（天气、新闻、股票、汇率等），你必须先使用 web_search 工具获取最新数据，不能凭记忆回答。**

工具使用要求：
- web_search 是唯一获取实时数据的途径
- 搜索结果中的信息才是你回答的依据
- 如果搜索没有结果，如实告诉用户未能获取到数据"""


# 需要实时搜索的关键词
REALTIME_KEYWORDS = ['天气', 'weather', '温度', '气温', '新闻', 'news', '股票', 'stock',
                     '汇率', 'rate', '今天', '现在', '实时', '最新', '当前', '预报', 'forecast']


def get_worker_config_service():
    """获取Worker配置服务实例"""
    from app.main import app_state
    return app_state.worker_config_service


def get_task_service():
    """获取TaskService实例"""
    from app.main import app_state
    return app_state.task_service


@router.post("/send")
async def chat_send(request: ChatRequest):
    """发送消息，自动判断是直接回答还是编程任务"""
    if not request.user_input or not request.user_input.strip():
        raise HTTPException(status_code=400, detail="请输入内容")

    user_input = request.user_input.strip()

    try:
        # 获取 Leader 的 LLM 配置
        config_service = get_worker_config_service()
        leader_config = await config_service.get_config("leader")
        if not leader_config:
            # 回退默认配置
            from app.config import DEFAULT_WORKER_CONFIG
            llm_config = dict(DEFAULT_WORKER_CONFIG)
            import os
            llm_config["api_key"] = os.getenv("DEEPSEEK_API_KEY", "")
            llm_config["api_base_url"] = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        else:
            from app.utils.crypto import decrypt_api_key
            api_key = decrypt_api_key(leader_config.api_key or "")
            llm_config = {
                "api_key": api_key,
                "api_base_url": leader_config.api_base_url or "https://api.deepseek.com/v1",
                "model_name": leader_config.model_name or "deepseek-v4-flash",
                "temperature": 0.1,  # 分类用低温度
                "max_tokens": 512,
            }

        # 第一步：分类 - 简单问答还是编程任务
        classification = await LLMFactory.chat(
            "leader", llm_config,
            f"用户输入：{user_input}\n\n请判断类型：",
            CLASSIFY_SYSTEM_PROMPT,
        )

        # 解析分类结果
        try:
            classification = classification.strip()
            if classification.startswith("```"):
                lines = classification.split("\n")
                if len(lines) > 2:
                    classification = "\n".join(lines[1:-1])
            result = json.loads(classification)
            chat_type = result.get("type", "direct")
        except (json.JSONDecodeError, KeyError):
            logger.warning(f"分类结果解析失败: {classification[:100]}")
            chat_type = "direct"  # 默认直接回答

        # 第二步：根据不同类型处理
        if chat_type == "task":
            # 编程任务 → 走现有任务创建流程
            task_service = get_task_service()
            task_id = await task_service.create_task_record(user_input)
            position = await task_service.enqueue_task(task_id, user_input)

            return {
                "type": "task",
                "task_id": task_id,
                "queue_position": position,
            }
        else:
            # 简单问答 → 使用工具增强回答
            llm_config["temperature"] = 0.3
            llm_config["max_tokens"] = 2048

            # 预检测：如果是天气/实时信息查询，先强制获取搜索数据
            realtime_context = ""
            if any(kw in user_input for kw in REALTIME_KEYWORDS):
                try:
                    search_result = await ToolRegistry.execute("web_search", {"query": user_input})
                    if search_result and search_result.success and search_result.data:
                        realtime_context = f"\n\n【实时搜索结果】\n{json.dumps(search_result.data[:3], ensure_ascii=False, indent=2)}\n\n请基于以上实时信息回答用户。如果搜索信息充足，直接给出答案；如果不充分，补充你所知道的。"
                except Exception as se:
                    logger.warning(f"Pre-fetch search failed: {se}")

            # 构造带实时上下文的提示词
            enhanced_system = DIRECT_ANSWER_SYSTEM + realtime_context

            tools = ToolRegistry.get_tool_defs(["search"])
            answer, records = await LLMFactory.chat_with_tools(
                "leader", llm_config,
                user_input,
                system_prompt=enhanced_system,
                tools=tools,
                max_tool_rounds=3,
            )

            logger.info(f"直接回答工具调用记录: {len(records)} 次")

            return {
                "type": "direct",
                "content": answer.strip(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"对话处理失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
