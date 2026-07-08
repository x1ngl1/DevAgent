"""Leader Agent - 任务拆解、主持讨论与调度"""
import json
import asyncio
import logging
from typing import Dict, Any, List

from app.agents.base import AgentBase
from app.utils.prompt_templates import (
    LEADER_DECOMPOSE_SYSTEM,
    LEADER_SUMMARIZE_SYSTEM,
    LEADER_CHECK_CONSENSUS_SYSTEM,
    LEADER_DISCUSS_SUMMARY_SYSTEM,
    LEADER_DECOMPOSE_WITH_TOOLS,
)

logger = logging.getLogger(__name__)


class LeaderAgent(AgentBase):
    """Leader Agent：拆解任务、主持团队讨论、调度Worker、汇总结果"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("leader", config)

    async def decompose(self, user_input: str) -> Dict:
        """拆解用户需求为子任务清单（使用工具获取实时信息）"""
        await self._update_status("running", {"phase": "decompose"})

        try:
            # 使用 chat_with_tools 支持搜索工具
            prompt = f"""用户需求：{user_input}

如果用户需要实时信息（如天气、新闻、股票等），请先使用 web_search 工具获取数据。
如果需要调用外部 API，请使用 http_request 工具。

获取到实时数据后，再拆解任务或直接回复用户。"""

            response = await self.chat_with_tools(
                prompt=prompt,
                system_prompt=LEADER_DECOMPOSE_WITH_TOOLS,
            )
            result = self.parse_json_response(response)
            subtasks = result.get("subtasks", [])

            await self._update_status("done", {
                "phase": "decompose",
                "subtask_count": len(subtasks),
                "subtasks": subtasks,
                "realtime_data": result.get("realtime_data", ""),
            })
            return result

        except Exception as e:
            logger.error(f"Leader拆解失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise

    async def check_consensus(self, user_input: str, discussion_log: List[Dict]) -> Dict:
        """判断团队是否已达成共识"""
        try:
            response = await self.chat(
                prompt=f"用户需求：{user_input}\n\n讨论记录：\n{json.dumps(discussion_log, ensure_ascii=False, indent=2)}",
                system_prompt=LEADER_CHECK_CONSENSUS_SYSTEM,
            )
            return self.parse_json_response(response)
        except Exception as e:
            logger.warning(f"共识判断失败: {e}")
            return {"consensus": True, "remaining_concerns": ""}

    async def summarize_discussion(self, user_input: str, discussion_log: List[Dict], consensus: bool) -> Dict:
        """总结团队讨论"""
        try:
            status_text = "已达成共识" if consensus else "未完全达成共识，按多数意见执行"
            response = await self.chat(
                prompt=f"用户需求：{user_input}\n\n讨论记录：\n{json.dumps(discussion_log, ensure_ascii=False, indent=2)}\n\n讨论状态：{status_text}",
                system_prompt=LEADER_DISCUSS_SUMMARY_SYSTEM,
            )
            return self.parse_json_response(response)
        except Exception as e:
            logger.warning(f"讨论总结失败: {e}")
            return {"summary": "讨论结束，开始执行。"}

    async def generate_summary(
        self,
        user_input: str,
        coder_result: Dict = None,
        pm_result: Dict = None,
        tester_result: Dict = None,
        realtime_data: str = None,
    ) -> str:
        """生成最终汇总报告"""
        context = {
            "user_input": user_input,
            "coder": coder_result or {},
            "pm": pm_result or {},
            "tester": tester_result or {},
            "realtime_data": realtime_data or "",
        }

        realtime_section = f"\n### 实时数据\n{realtime_data}\n" if realtime_data else ""

        prompt = f"""用户需求：{user_input}

## 执行结果汇总

### 代码产出
{json.dumps(coder_result, ensure_ascii=False, indent=2) if coder_result else "无"}

### PM审核结果
{json.dumps(pm_result, ensure_ascii=False, indent=2) if pm_result else "无"}

### 测试结果
{json.dumps(tester_result, ensure_ascii=False, indent=2) if tester_result else "无"}
{realtime_section}
请生成给用户的最终报告。"""

        try:
            response = await self.chat(
                prompt=prompt,
                system_prompt=LEADER_SUMMARIZE_SYSTEM,
            )
            return response
        except Exception as e:
            logger.error(f"Leader汇总失败: {e}")
            return f"任务已完成！所有工作已就绪，请查看产出文件。"
