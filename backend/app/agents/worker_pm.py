"""PM Agent - 测试代码质量审核 & 覆盖率评估 & 参与讨论"""
import json
import logging
from typing import Dict, Any

from app.agents.base import AgentBase
from app.utils.prompt_templates import (
    PM_REVIEW_SYSTEM, PM_TEST_EVAL_SYSTEM, PM_DISCUSS_SYSTEM, PM_SYSTEM_WITH_TOOLS,
)

logger = logging.getLogger(__name__)


class PMWorker(AgentBase):
    """PM Agent：审核测试代码质量，评估覆盖率，参与团队讨论"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("pm", config)

    async def discuss(self, context: Dict, coder_opinion: str = "") -> Dict:
        """参与团队讨论，从质量角度评审测试方案"""
        await self._update_status("running", {"phase": "discussing"})
        try:
            user_input = context.get("user_input", "")

            response = await self.chat(
                prompt=f"需要测试的代码：{user_input}\n\n测试方案：{coder_opinion}",
                system_prompt=PM_DISCUSS_SYSTEM,
            )
            result = self.parse_json_response(response)

            await self._update_status("done", {"phase": "discussing"})
            return result
        except Exception as e:
            logger.error(f"PM讨论失败: {e}")
            await self._update_status("error", {"error": str(e)})
            return {"opinion": "测试方案可行。", "risks": ""}

    async def review_code(self, test_code: str, source_code: str = "",
                          pytest_output: str = "", coverage_report: str = "") -> Dict:
        """审核测试代码质量（硬指标+软指标混合评分）

        Args:
            test_code: 测试代码内容
            source_code: 被测函数源代码
            pytest_output: pytest 执行输出
            coverage_report: 覆盖率报告文本

        Returns:
            dict: 包含 score, decision, issues 等字段
        """
        await self._update_status("running", {"phase": "review"})

        try:
            prompt = f"""请审核以下单元测试代码。

## 测试代码
```python
{test_code}
```

## 被测函数源代码
```python
{source_code}
```

## pytest 执行结果
{pytest_output if pytest_output else "（未执行）"}

## 覆盖率报告
{coverage_report if coverage_report else "（暂无覆盖率数据）"}

请按评分体系进行综合评分。"""

            response = await self.chat_with_tools(
                prompt=prompt,
                system_prompt=PM_SYSTEM_WITH_TOOLS,
            )
            result = self.parse_json_response(response)

            # 确保关键字段存在
            if "score" not in result:
                result["score"] = 0
            if "decision" not in result:
                result["decision"] = "escalate" if result.get("score", 0) < 60 else "pass"
            if "pass" not in result:
                result["pass"] = result.get("decision") in ("pass", "pass_with_warning")

            await self._update_status("done", {
                "phase": "review",
                "score": result.get("score"),
                "hard_score": result.get("hard_score", 0),
                "soft_score": result.get("soft_score", 0),
                "decision": result.get("decision"),
                "summary": result.get("summary", ""),
                "issues": result.get("issues", []),
            })
            return result

        except Exception as e:
            logger.error(f"PM审核失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise

    async def evaluate_test_results(self, test_output: str, coverage_data: Dict) -> Dict:
        """评估测试执行结果和覆盖率"""
        await self._update_status("running", {"phase": "evaluate_test"})

        try:
            coverage_str = json.dumps(coverage_data, ensure_ascii=False, indent=2) if coverage_data else "无"

            prompt = f"""测试执行结果：
{test_output}

覆盖率数据：
{coverage_str}

请评估测试结果是否达标。"""

            response = await self.chat(
                prompt=prompt,
                system_prompt=PM_TEST_EVAL_SYSTEM,
            )
            result = self.parse_json_response(response)
            result["coverage_data"] = coverage_data

            await self._update_status("done", {
                "phase": "evaluate_test",
                "decision": result.get("decision"),
                "coverage": coverage_data.get("line_rate", 0) if coverage_data else 0,
                "summary": result.get("summary", ""),
            })
            return result

        except Exception as e:
            logger.error(f"PM评估测试失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise
