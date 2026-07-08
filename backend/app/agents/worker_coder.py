"""程序员Worker - 编写业务代码 & 参与讨论"""
import json
import logging
from typing import Dict, Any

from app.agents.base import AgentBase
from app.utils.prompt_templates import CODER_SYSTEM, CODER_DISCUSS_SYSTEM, CODER_SYSTEM_WITH_TOOLS

logger = logging.getLogger(__name__)


class CoderWorker(AgentBase):
    """程序员Worker：编写业务代码和README，参与团队讨论"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("coder", config)

    async def discuss(self, context: Dict) -> Dict:
        """参与团队讨论，提出技术意见"""
        await self._update_status("running", {"phase": "discussing"})
        try:
            user_input = context.get("user_input", "")
            subtask_summary = context.get("subtask_summary", "")
            prev_discussion = context.get("discussion_log", [])
            prev_text = json.dumps(prev_discussion, ensure_ascii=False, indent=2) if prev_discussion else "无"

            response = await self.chat(
                prompt=f"用户需求：{user_input}\n\n任务拆解：\n{subtask_summary}\n\n已有讨论：\n{prev_text}",
                system_prompt=CODER_DISCUSS_SYSTEM,
            )
            result = self.parse_json_response(response)

            await self._update_status("done", {"phase": "discussing"})
            return result
        except Exception as e:
            logger.error(f"Coder讨论失败: {e}")
            await self._update_status("error", {"error": str(e)})
            return {"opinion": "方案可行，准备实施。", "concerns": ""}

    async def write_code(self, task_description: str) -> Dict:
        """根据任务描述编写代码（使用工具辅助）"""
        await self._update_status("running", {"phase": "writing"})

        try:
            # 使用 chat_with_tools 替代 chat，支持工具调用
            prompt = f"""任务描述：{task_description}

你可以使用以下工具辅助完成任务：
- web_search: 搜索相关技术资料和最佳实践
- run_python: 快速验证代码片段
- analyze_code: 分析已有代码结构
- read_project_file: 读取已有文件内容
- query_codebase: 搜索代码库中的相关代码

请完成编码任务，输出JSON格式的代码文件。"""

            response = await self.chat_with_tools(
                prompt=prompt,
                system_prompt=CODER_SYSTEM_WITH_TOOLS,
            )
            result = self.parse_json_response(response)

            files = result.get("files", {})
            file_list = list(files.keys())
            import logging as _lg; _lg.getLogger(__name__).info(f"Coder raw response: {str(result)[:500]}")
            if not file_list:
                _lg.getLogger(__name__).warning(f"Coder produced 0 files! Full result: {json.dumps(result, ensure_ascii=False)[:1000]}")

            await self._update_status("done", {
                "phase": "writing",
                "files": file_list,
                "summary": result.get("summary", ""),
                "language": result.get("language", "Python"),
            })
            return result

        except Exception as e:
            logger.error(f"程序员编码失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise
