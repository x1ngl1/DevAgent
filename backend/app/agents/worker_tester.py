"""测试执行Worker - 运行测试 & 收集覆盖率 & 参与讨论"""
import json
import logging
import os
from typing import Dict, Any

from app.agents.base import AgentBase
from app.utils.prompt_templates import TESTER_SYSTEM, TESTER_DISCUSS_SYSTEM, TESTER_SYSTEM_WITH_TOOLS
from app.services.evaluator import (
    parse_coverage_report,
    parse_coverage_from_pytest_output,
    pytest_output_parser,
    summarize_test_results,
)

logger = logging.getLogger(__name__)


class TesterWorker(AgentBase):
    """测试执行Worker：运行单元测试、收集覆盖率数据、参与团队讨论"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("tester", config)

    async def discuss(self, context: Dict, coder_opinion: str = "") -> Dict:
        """参与团队讨论，提出测试策略"""
        await self._update_status("running", {"phase": "discussing"})
        try:
            user_input = context.get("user_input", "")

            response = await self.chat(
                prompt=f"需要测试的代码：{user_input}\n\n测试方案：{coder_opinion}",
                system_prompt=TESTER_DISCUSS_SYSTEM,
            )
            result = self.parse_json_response(response)

            await self._update_status("done", {"phase": "discussing"})
            return result
        except Exception as e:
            logger.error(f"Tester讨论失败: {e}")
            await self._update_status("error", {"error": str(e)})
            return {"opinion": "可以编写测试覆盖核心功能。", "test_cases": ""}

    async def write_tests(self, code_content: str, task_description: str = "") -> Dict:
        """根据代码编写测试用例（使用工具辅助）"""
        await self._update_status("running", {"phase": "writing_tests"})

        try:
            prompt = f"""任务描述：{task_description}

需要测试的代码：
```python
{code_content}
```

请编写完整的单元测试，要求：
1. 使用 pytest 框架
2. 覆盖正常情况、边界情况和异常情况
3. 生成 coverage.xml 覆盖率报告
4. 使用 --cov-report=xml 和 --cov-report=term 参数"""

            response = await self.chat_with_tools(
                prompt=prompt,
                system_prompt=TESTER_SYSTEM_WITH_TOOLS,
            )
            result = self.parse_json_response(response)

            test_files = result.get("test_files", {})
            test_file_list = list(test_files.keys())
            test_command = result.get("test_command", "pytest test_*.py -v --cov=. --cov-report=term --cov-report=xml")

            await self._update_status("done", {
                "phase": "writing_tests",
                "test_files": test_file_list,
                "summary": result.get("summary", ""),
                "test_command": test_command,
            })
            return {
                **result,
                "test_command": test_command,
            }

        except Exception as e:
            logger.error(f"测试编写失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise

    def parse_test_results(self, sandbox_output: Dict, coverage_xml_path: str = "") -> Dict:
        """解析测试执行结果，提取覆盖率数据

        Args:
            sandbox_output: Docker 沙箱返回的执行结果
            coverage_xml_path: coverage.xml 的路径（可选）

        Returns:
            dict: 包含覆盖率详情和测试计数
        """
        output_text = sandbox_output.get("output", "") if isinstance(sandbox_output, dict) else str(sandbox_output)

        # 1. 从 pytest 输出解析覆盖率
        coverage_pct = parse_coverage_from_pytest_output(output_text)

        # 2. 从 coverage.xml 解析详细数据（如果提供路径）
        coverage_detail = {}
        if coverage_xml_path and os.path.exists(coverage_xml_path):
            coverage_detail = parse_coverage_report(coverage_xml_path)

        # 3. 解析 pytest 输出中的测试计数
        test_counts = pytest_output_parser(output_text)

        # 4. 汇总结果
        summary = summarize_test_results(
            passed=test_counts.get("passed", 0),
            failed=test_counts.get("failed", 0),
            skipped=test_counts.get("skipped", 0),
            error=test_counts.get("errors", 0),
            coverage=coverage_pct,
        )

        result = {
            "sandbox_output": output_text,
            "coverage_pct": coverage_pct,
            "coverage_detail": coverage_detail or {
                "line_rate": coverage_pct / 100.0,
                "grade": "good" if coverage_pct >= 80 else "fair" if coverage_pct >= 60 else "poor",
            },
            "test_counts": test_counts,
            "summary": summary,
        }

        logger.info(f"测试结果解析完成: 覆盖率 {coverage_pct:.1f}%, "
                     f"通过 {test_counts.get('passed', 0)}/{sum(test_counts.values())}")

        return result
