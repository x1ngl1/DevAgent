"""对话管理器 — 协调团队多轮讨论"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable

from app.agents.leader import LeaderAgent
from app.agents.worker_coder import CoderWorker
from app.agents.worker_pm import PMWorker
from app.agents.worker_tester import TesterWorker
from app.utils.prompt_templates import (
    LEADER_CHECK_CONSENSUS_SYSTEM,
    LEADER_DISCUSS_SUMMARY_SYSTEM,
    CODER_DISCUSS_SYSTEM,
    PM_DISCUSS_SYSTEM,
    TESTER_DISCUSS_SYSTEM,
)

logger = logging.getLogger(__name__)

MAX_DISCUSSION_ROUNDS = 2  # 最多讨论轮数


class ConversationService:
    """团队对话管理器 — 在任务执行前组织多Agent讨论"""

    def __init__(self, worker_config_service, sse_callback: Callable):
        self.worker_config_service = worker_config_service
        self._sse_callback = sse_callback

    async def _emit(self, event_type: str, data: dict):
        if self._sse_callback:
            await self._sse_callback(event_type, data)

    async def _speak(self, role: str, content: str, zip_url: str = None, phase: str = "discussion"):
        """Agent发言（推送到前端聊天区）"""
        msg = {"role": role, "content": content, "phase": phase}
        if zip_url:
            msg["zip_url"] = zip_url
        await self._emit("chat_message", msg)
        await asyncio.sleep(0.25)

    async def _get_worker_config(self, worker_id: str) -> Dict:
        """获取 Worker 的 LLM 配置"""
        from app.utils.crypto import decrypt_api_key
        cfg = await self.worker_config_service.get_config(worker_id)
        if cfg:
            return {
                "api_key": decrypt_api_key(cfg.api_key or ""),
                "api_base_url": cfg.api_base_url or "https://api.deepseek.com/v1",
                "model_name": cfg.model_name or "deepseek-v4-flash",
                "temperature": cfg.temperature or 0.3,
                "max_tokens": cfg.max_tokens or 4096,
                "timeout": cfg.timeout or 30,
            }
        import os
        return {
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "api_base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            "model_name": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            "temperature": 0.3,
            "max_tokens": 4096,
            "timeout": 30,
        }

    async def team_discuss(
        self,
        user_input: str,
        subtasks: List[Dict],
    ) -> Dict:
        """团队讨论：Leader 主持 → Coder 提议 → PM 评审 → Tester 建议 → Leader 总结"""
        leader_config = await self._get_worker_config("leader")
        coder_config = await self._get_worker_config("coder")
        pm_config = await self._get_worker_config("pm")
        tester_config = await self._get_worker_config("tester")

        leader = LeaderAgent(leader_config)
        coder = CoderWorker(coder_config)
        pm = PMWorker(pm_config)
        tester = TesterWorker(tester_config)

        subtask_summary = "\n".join(
            f"  - {st['role']}: {st.get('description', '')}" for st in subtasks
        )
        context = {
            "user_input": user_input,
            "subtasks": subtasks,
            "subtask_summary": subtask_summary,
        }

        await self._speak("leader", f"团队讨论开始，各成员请就本次任务发表意见。\n需求：{user_input}")

        discussion_log = []
        consensus = False
        current_context = context

        for 轮_num in range(1, MAX_DISCUSSION_ROUNDS + 1):
            轮_label = f"第{轮_num}轮"

            # 1. Coder 发言
            await self._speak("coder", f"{轮_label}：分析任务并提出实现方案...")
            try:
                coder_view = await coder.discuss(current_context)
                coder_msg = coder_view.get("opinion", "")
                coder_concerns = coder_view.get("concerns", "")
                await self._speak("coder", coder_msg)
                if coder_concerns:
                    await self._speak("coder", f"注意事项：{coder_concerns}")
            except Exception as e:
                logger.warning(f"Coder 讨论发言失败: {e}")
                coder_msg = "方案可行，准备实施。"
                await self._speak("coder", coder_msg)

            await asyncio.sleep(0.1)

            # 2. PM 发言
            await self._speak("pm", f"{轮_label}：评审方案质量和风险...")
            try:
                pm_view = await pm.discuss(current_context, coder_msg)
                pm_msg = pm_view.get("opinion", "")
                pm_risks = pm_view.get("risks", "")
                await self._speak("pm", pm_msg)
                if pm_risks:
                    await self._speak("pm", f"风险提示：{pm_risks}")
            except Exception as e:
                logger.warning(f"PM 讨论发言失败: {e}")
                pm_msg = "方案可行。"
                await self._speak("pm", pm_msg)

            await asyncio.sleep(0.1)

            # 3. Tester 发言
            await self._speak("tester", f"{轮_label}：提出测试策略...")
            try:
                tester_view = await tester.discuss(current_context, coder_msg)
                tester_msg = tester_view.get("opinion", "")
                tester_cases = tester_view.get("test_cases", "")
                await self._speak("tester", tester_msg)
                if tester_cases:
                    await self._speak("tester", f"测试要点：{tester_cases}")
            except Exception as e:
                logger.warning(f"Tester 讨论发言失败: {e}")
                tester_msg = "可以编写测试覆盖核心功能。"
                await self._speak("tester", tester_msg)

            await asyncio.sleep(0.1)

            discussion_log.append({
                "轮": 轮_num,
                "coder": coder_msg,
                "pm": pm_msg,
                "tester": tester_msg,
            })

            # 4. Leader 判断是否达成共识
            try:
                consensus_check = await leader.check_consensus(
                    user_input, discussion_log
                )
                consensus = consensus_check.get("consensus", False)
                if consensus:
                    await self._speak("leader", "团队已达成共识，开始执行。")
                    break
                else:
                    concerns = consensus_check.get("remaining_concerns", "")
                    if concerns:
                        await self._speak("leader", f"需要进一步讨论：{concerns}")
                    # 更新 context 供下一轮讨论
                    current_context["discussion_log"] = discussion_log
            except Exception as e:
                logger.warning(f"Leader 共识判断失败: {e}")
                if 轮_num >= MAX_DISCUSSION_ROUNDS:
                    consensus = True
                break

        # Leader 总结
        try:
            summary = await leader.summarize_discussion(
                user_input, discussion_log, consensus
            )
            await self._speak("leader", summary.get("summary", "讨论结束，开始执行。"))
        except Exception as e:
            logger.warning(f"讨论总结失败: {e}")
            await self._speak("leader", "讨论结束，开始执行。")

        return {
            "consensus": consensus,
            "轮s": len(discussion_log),
            "discussion_log": discussion_log,
            "summary": summary.get("summary", "") if 'summary' in locals() else "",
        }
