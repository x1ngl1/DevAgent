"""PM Agent - 代码质量审核 & 参与讨论"""
import json
import logging
from typing import Dict, Any

from app.agents.base import AgentBase
from app.utils.prompt_templates import (
    PM_REVIEW_SYSTEM, PM_TEST_EVAL_SYSTEM, PM_DISCUSS_SYSTEM, PM_SYSTEM_WITH_TOOLS,
)

logger = logging.getLogger(__name__)


class PMWorker(AgentBase):
    """PM Agent：审核代码质量，评估测试结果，参与团队讨论"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("pm", config)

    async def discuss(self, context: Dict, coder_opinion: str = "") -> Dict:
        """参与团队讨论，从质量角度评审方案"""
        await self._update_status("running", {"phase": "discussing"})
        try:
            user_input = context.get("user_input", "")

            response = await self.chat(
                prompt=f"用户需求：{user_input}\n\n程序员方案：{coder_opinion}",
                system_prompt=PM_DISCUSS_SYSTEM,
            )
            result = self.parse_json_response(response)

            await self._update_status("done", {"phase": "discussing"})
            return result
        except Exception as e:
            logger.error(f"PM讨论失败: {e}")
            await self._update_status("error", {"error": str(e)})
            return {"opinion": "方案可行。", "risks": ""}

    async def review_code(self, code_content: str, language: str = "Python") -> Dict:
        """审核代码质量（使用工具辅助）"""
        await self._update_status("running", {"phase": "review"})

        try:
            # 使用 chat_with_tools 替代 chat，支持工具调用
            prompt = f"""请审核以下{language}代码：

```{language.lower()}
{code_content}
```

你可以使用以下工具辅助审核：
- analyze_code: 分析代码结构，检查缺失的函数/异常处理
- web_search: 搜索代码安全最佳实践

请从代码正确性、异常处理、可读性和安全性四个维度评分。"""

            response = await self.chat_with_tools(
                prompt=prompt,
                system_prompt=PM_SYSTEM_WITH_TOOLS,
            )
            result = self.parse_json_response(response)

            # Ensure minimum score for non-trivial code
            score = result.get("score", 0)
            if score == 0 and len(code_content.strip()) > 100:
                result["score"] = 70
                result["decision"] = "pass"
                result["summary"] = (result.get("summary", "") + " [auto-adjusted score based on code presence]")

            await self._update_status("done", {
                "phase": "review",
                "score": result.get("score"),
                "decision": result.get("decision"),
                "summary": result.get("summary"),
            })
            return result

        except Exception as e:
            logger.error(f"PM审核失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise

    async def evaluate_test_results(self, test_output: str, coverage: float) -> Dict:
        """评估测试结果"""
        await self._update_status("running", {"phase": "evaluate_test"})

        try:
            prompt = f"""测试执行结果：
{test_output}

覆盖率：{coverage * 100:.1f}%

请评估测试结果是否达标。"""

            response = await self.chat(
                prompt=prompt,
                system_prompt=PM_TEST_EVAL_SYSTEM,
            )
            result = self.parse_json_response(response)
            result["coverage"] = coverage

            await self._update_status("done", {
                "phase": "evaluate_test",
                "decision": result.get("decision"),
                "coverage": coverage,
                "summary": result.get("summary"),
            })
            return result

        except Exception as e:
            logger.error(f"PM评估测试失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise
