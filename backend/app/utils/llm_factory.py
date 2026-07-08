"""LLM factory - tool calling and streaming support (LangChain internal)"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Tuple, AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from app.utils.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class LLMFactory:
    _clients: Dict[str, ChatOpenAI] = {}
    MAX_RETRIES = 3

    @classmethod
    def get_client(cls, worker_id: str, config: Dict[str, Any]) -> ChatOpenAI:
        api_key = config.get("api_key", "")
        base_url = config.get("api_base_url", "")
        cache_key = f"{worker_id}|{base_url}"
        if cache_key not in cls._clients:
            cls._clients[cache_key] = ChatOpenAI(
                model=config.get("model_name"),
                api_key=api_key,
                base_url=base_url,
                temperature=config.get("temperature", 0.3),
                max_tokens=config.get("max_tokens", 4096),
                timeout=config.get("timeout", 30),
            )
        return cls._clients[cache_key]

    @classmethod
    async def chat(cls, worker_id: str, config: Dict[str, Any], prompt: str,
                   system_prompt: Optional[str] = None) -> str:
        last_error = None
        for attempt in range(1, cls.MAX_RETRIES + 1):
            try:
                llm = cls.get_client(worker_id, config)
                messages = []
                if system_prompt:
                    messages.append(SystemMessage(content=system_prompt))
                messages.append(HumanMessage(content=prompt))
                response = await llm.ainvoke(messages)
                return response.content
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call failed (attempt {attempt}/{cls.MAX_RETRIES}) worker={worker_id}: {str(e)[:100]}")
                if attempt < cls.MAX_RETRIES:
                    await asyncio.sleep(2 ** (attempt - 1))
        raise last_error

    @classmethod
    async def chat_with_tools(
        cls, worker_id: str, config: Dict[str, Any], prompt: str,
        system_prompt: Optional[str] = None, tools: Optional[List[Dict]] = None,
        tool_categories: Optional[List[str]] = None, max_tool_rounds: int = 5,
        stream_callback: Optional[callable] = None,
    ) -> Tuple[str, List[Dict]]:
        if not tools and tool_categories:
            tools = ToolRegistry.get_tool_defs(tool_categories)
        tools = tools or []
        last_error = None
        all_records = []

        for attempt in range(1, cls.MAX_RETRIES + 1):
            try:
                llm = cls.get_client(worker_id, config)
                # 用 LangChain 消息对象替换 dict 消息
                messages: list = []
                if system_prompt:
                    messages.append(SystemMessage(content=system_prompt))
                messages.append(HumanMessage(content=prompt))

                for round_idx in range(max_tool_rounds):
                    # 绑定工具调用
                    llm_with_tools = llm.bind_tools(tools, tool_choice="auto")
                    response = await llm_with_tools.ainvoke(messages)

                    if not response.tool_calls:
                        if stream_callback:
                            await stream_callback({"type": "final", "content": response.content or ""})
                        return response.content or "", all_records

                    # 将 AI 回复加入消息列表
                    messages.append(response)

                    # 构造 ToolRegistry 需要的调用格式
                    tc_list = []
                    for tc in response.tool_calls:
                        tc_list.append({
                            "id": tc.get("id", ""),
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False),
                            }
                        })

                    # 执行工具（结果依旧是 dict 格式）
                    tool_messages = await ToolRegistry.execute_tool_calls(
                        tc_list,
                        {"worker_id": worker_id, "round": round_idx},
                    )

                    # 将工具执行结果转为 LangChain ToolMessage
                    for tm in tool_messages:
                        if isinstance(tm, dict):
                            messages.append(ToolMessage(
                                content=tm.get("content", ""),
                                tool_call_id=tm.get("tool_call_id", ""),
                            ))
                        else:
                            messages.append(tm)

                    # 记录工具调用
                    for tc in response.tool_calls:
                        all_records.append({
                            "tool_name": tc.get("name", ""),
                            "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False),
                            "round": round_idx,
                        })

                    if stream_callback:
                        names = [tc.get("name", "") for tc in response.tool_calls]
                        await stream_callback({"type": "tool_calls", "tools": names, "round": round_idx})

                # 超过最大轮次，强制获取最终回复
                final = await llm.ainvoke(messages)
                result = final.content or ""
                if stream_callback:
                    await stream_callback({"type": "final", "content": result})
                return result, all_records

            except Exception as e:
                last_error = e
                logger.warning(f"Tool calling failed (attempt {attempt}/{cls.MAX_RETRIES}): {str(e)[:100]}")
                if attempt < cls.MAX_RETRIES:
                    await asyncio.sleep(2 ** (attempt - 1))
        raise last_error

    @classmethod
    async def chat_stream(cls, worker_id: str, config: Dict[str, Any], prompt: str,
                          system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        llm = cls.get_client(worker_id, config)
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield chunk.content

    @classmethod
    def clear_cache(cls):
        cls._clients.clear()