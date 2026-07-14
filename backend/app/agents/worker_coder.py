"""测试工程师Worker - 为指定函数编写单元测试 & 参与讨论"""
import json
import logging
from typing import Dict, Any

from app.agents.base import AgentBase
from app.utils.prompt_templates import CODER_TEST_SYSTEM, CODER_DISCUSS_SYSTEM, CODER_SYSTEM_WITH_TOOLS

logger = logging.getLogger(__name__)


class CoderWorker(AgentBase):
    """测试工程师Worker：为指定函数编写单元测试，参与团队讨论"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("coder", config)

    async def discuss(self, context: Dict) -> Dict:
        """参与团队讨论，提出测试策略意见"""
        await self._update_status("running", {"phase": "discussing"})
        try:
            user_input = context.get("user_input", "")
            subtask_summary = context.get("subtask_summary", "")
            prev_discussion = context.get("discussion_log", [])
            prev_text = json.dumps(prev_discussion, ensure_ascii=False, indent=2) if prev_discussion else "无"

            response = await self.chat(
                prompt=f"需要测试的代码：{user_input}\n\n测试任务拆解：\n{subtask_summary}\n\n已有讨论：\n{prev_text}",
                system_prompt=CODER_DISCUSS_SYSTEM,
            )
            result = self.parse_json_response(response)

            await self._update_status("done", {"phase": "discussing"})
            return result
        except Exception as e:
            logger.error(f"Coder讨论失败: {e}")
            await self._update_status("error", {"error": str(e)})
            return {"opinion": "测试方案可行，准备实施。", "concerns": ""}

    async def write_tests(self, function_code: str, function_name: str = "",
                          signature: str = "", dependencies: list = None) -> Dict:
        """为指定函数编写单元测试

        Args:
            function_code: 函数的源代码
            function_name: 函数名
            signature: 函数签名描述
            dependencies: 依赖的外部库列表

        Returns:
            dict: 包含 test_code, test_file, summary 等字段
        """
        await self._update_status("running", {"phase": "writing_tests"})

        try:
            deps_str = ", ".join(dependencies) if dependencies else "无"

            prompt = f"""需要测试的函数名称：{function_name}

函数签名：{signature}

函数源代码：
```python
{function_code}
```

依赖的外部库：{deps_str}

请编写完整的 pytest 单元测试，覆盖所有重要场景。"""

            response = await self.chat_with_tools(
                prompt=prompt,
                system_prompt=CODER_SYSTEM_WITH_TOOLS,
            )
            result = self.parse_json_response(response)

            test_code = result.get("test_code", "")
            test_file = result.get("test_file", f"test_{function_name}.py")
            scenarios = result.get("test_scenarios", [])

            # 构造统一的 files 格式
            files = {test_file: test_code}
            file_list = list(files.keys())

            logger.info(f"Coder 生成测试: {test_file}, 场景: {scenarios}")

            await self._update_status("done", {
                "phase": "writing_tests",
                "files": file_list,
                "summary": result.get("summary", f"为 {function_name} 生成了测试"),
                "language": result.get("language", "Python"),
                "test_scenarios": scenarios,
            })
            return {
                "files": files,
                "summary": result.get("summary", f"为 {function_name} 生成了 {len(scenarios)} 个测试场景"),
                "language": result.get("language", "Python"),
                "test_scenarios": scenarios,
                "test_file": test_file,
            }

        except Exception as e:
            logger.error(f"测试编写失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise
