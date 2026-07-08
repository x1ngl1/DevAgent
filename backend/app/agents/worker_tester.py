"""测试工程师Worker - 编写测试 & 参与讨论"""
import json
import logging
from typing import Dict, Any

from app.agents.base import AgentBase
from app.utils.prompt_templates import TESTER_SYSTEM, TESTER_DISCUSS_SYSTEM, TESTER_SYSTEM_WITH_TOOLS

logger = logging.getLogger(__name__)


class TesterWorker(AgentBase):
    """测试工程师Worker：编写单元测试，参与团队讨论"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("tester", config)

    async def discuss(self, context: Dict, coder_opinion: str = "") -> Dict:
        """参与团队讨论，提出测试策略"""
        await self._update_status("running", {"phase": "discussing"})
        try:
            user_input = context.get("user_input", "")

            response = await self.chat(
                prompt=f"用户需求：{user_input}\n\n实现方案：{coder_opinion}",
                system_prompt=TESTER_DISCUSS_SYSTEM,
            )
            result = self.parse_json_response(response)

            await self._update_status("done", {"phase": "discussing"})
            return result
        except Exception as e:
            logger.error(f"Tester讨论失败: {e}")
            await self._update_status("error", {"error": str(e)})
            return {"opinion": "可以编写测试覆盖核心功能。", "test_cases": ""}

    async def write_tests(self, code_content: str, task_description: str) -> Dict:
        """根据代码编写测试用例（使用工具辅助）"""
        await self._update_status("running", {"phase": "writing_tests"})

        try:
            # 使用 chat_with_tools 替代 chat，支持工具调用
            prompt = f"""任务描述：{task_description}

需要测试的代码：
```python
{code_content}
```

你可以使用以下工具辅助测试编写：
- analyze_code: 分析代码结构，识别需要测试的函数
- run_python: 运行测试代码验证

请编写完整的单元测试，覆盖正常情况、边界情况和异常情况。"""

            response = await self.chat_with_tools(
                prompt=prompt,
                system_prompt=TESTER_SYSTEM_WITH_TOOLS,
            )
            result = self.parse_json_response(response)

            test_files = result.get("test_files", {})
            test_file_list = list(test_files.keys())

            await self._update_status("done", {
                "phase": "writing_tests",
                "test_files": test_file_list,
                "summary": result.get("summary", ""),
            })
            return result

        except Exception as e:
            logger.error(f"测试编写失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise
