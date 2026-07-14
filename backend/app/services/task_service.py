"""Task service - DAG parallel + streaming + checkpoint (Legacy Test Generation)"""
import asyncio, json, logging, os, traceback, time
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from app.config import CHECKPOINT_ENABLED, INTERVENTION_MODE
from app.agents.leader import LeaderAgent
from app.agents.worker_coder import CoderWorker
from app.agents.worker_pm import PMWorker
from app.agents.worker_tester import TesterWorker
from app.services.file_service import FileService
from app.services.sandbox import SandboxService
from app.services.conversation_service import ConversationService
from app.services.task_executor import DAGTaskExecutor, TaskDef
from app.services.stream_service import StreamService
from app.services.evaluator import parse_coverage_report, summarize_test_results, pytest_output_parser
from app.utils.tool_registry import register_builtin_tools, ToolRegistry
logger = logging.getLogger(__name__)
class TaskService:
    def __init__(self, dbf, wcs, rag_service=None):
        self.db = dbf; self.wcs = wcs; self.rag_service = rag_service
        self._sse_cb = None
        self._queue = asyncio.Queue(); self._lock = asyncio.Lock(); self._qw = None; self._pending = 0
        self.fs = FileService(); self.ss = SandboxService(); self.cs = None
        self._cancel = asyncio.Event(); self._current_task = None; self.stream = StreamService()
        self._paused = False; self._pause_ev = None
        self._iv_events = {}; self._iv_results = {}
        register_builtin_tools(); ToolRegistry.set_status_callback(self._tool_cb)
    async def _tool_cb(self, d):
        if self._sse_cb: await self._sse_cb("tool_call_progress", {"worker_id":"system",**d})
    def cancel_current_task(self):
        if self._cancel: self._cancel.set()
        # 立即取消正在执行的 asyncio task（LLM 调用阻塞时也能中断）
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            logger.info("Current task cancelled via task.cancel()")
    async def pause_current_task(self):
        self._paused = True; self._pause_ev = asyncio.Event()
        if self._sse_cb: await self._sse_cb("pause_state", {"paused":True}); logger.info("Paused")
    async def resume_current_task(self):
        self._paused = False
        if self._pause_ev: self._pause_ev.set(); self._pause_ev = None
        if self._sse_cb: await self._sse_cb("pause_state", {"paused":False}); logger.info("Resumed")
    async def send_intervention(self, rid, decision, feedback=""):
        ev = self._iv_events.get(rid)
        if ev: self._iv_results[rid] = {"decision":decision,"feedback":feedback}; ev.set()
    def _check_cancel(self):
        if self._cancel and self._cancel.is_set(): raise asyncio.CancelledError()
    async def _check_pause(self):
        while self._paused and self._pause_ev and not (self._cancel and self._cancel.is_set()):
            try: await asyncio.wait_for(self._pause_ev.wait(),1)
            except asyncio.TimeoutError: continue
    def set_conversation_service(self, svc): self.cs = svc
    async def create_task_record(self, inp, code_content: str = ""):
        from app.models.database import async_session_factory
        from app.models.task import Task
        tid = f"T{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(2).hex().upper()}"
        combined_input = code_content if code_content else inp
        async with async_session_factory() as s: s.add(Task(id=tid, user_input=combined_input, status="pending")); await s.commit()
        return tid
    def set_sse_callback(self, cb): self._sse_cb = cb; self.stream.set_sse_callback(cb)
    async def _emit(self, et, d):
        if self._sse_cb: await self._sse_cb(et, d)
    async def _chat(self, role, content, phase="execution", **kw):
        await self._emit("chat_message", {"role":role,"content":content,"phase":phase,**kw})

    async def _get_config(self, wid):
        cfg = await self.wcs.get_config(wid)
        if cfg:
            from app.utils.crypto import decrypt_api_key; ak = decrypt_api_key(cfg.api_key or "")
            return {"api_key":ak,"api_base_url":cfg.api_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1","model_name":cfg.model_name or "qwen-plus","temperature":cfg.temperature or 0.3,"max_tokens":cfg.max_tokens or 4096,"timeout":cfg.timeout or 30}
        return {"api_key":os.getenv("DEEPSEEK_API_KEY",""),"api_base_url":os.getenv("DEEPSEEK_BASE_URL","https://dashscope.aliyuncs.com/compatible-mode/v1"),"model_name":os.getenv("DEEPSEEK_MODEL","qwen-plus"),"temperature":0.3,"max_tokens":4096,"timeout":30}

    async def get_task(self, tid):
        async with self.db() as s:
            from app.models.task import Task
            from sqlalchemy import select; from sqlalchemy.orm import selectinload
            t = (await s.execute(select(Task).options(selectinload(Task.subtasks)).where(Task.id==tid))).scalar_one_or_none()
            if not t: return None
            return {"id":t.id,"user_input":t.user_input,"status":t.status,"zip_url":t.zip_url,"error_msg":t.error_msg,"checkpoint_data":t.checkpoint_data,"created_at":t.created_at.isoformat() if t.created_at else None,"finished_at":t.finished_at.isoformat() if t.finished_at else None,"subtasks":[{"id":s.id,"role":s.role,"description":s.description,"status":s.status} for s in t.subtasks]}

    async def get_subtasks(self, tid):
        async with self.db() as s:
            from app.models.task import Subtask; from sqlalchemy import select
            sts = (await s.execute(select(Subtask).where(Subtask.task_id==tid).order_by(Subtask.id))).scalars().all()
            return [{"id":st.id,"role":st.role,"description":st.description,"status":st.status,"output_summary":st.output_summary,"error_msg":st.error_msg,"duration":st.duration,"depends_on":st.depends_on} for st in sts]

    async def get_subtask_detail(self, tid, subtask_id):
        async with self.db() as s:
            from app.models.task import Subtask; from sqlalchemy import select
            st = (await s.execute(select(Subtask).where(Subtask.id==subtask_id, Subtask.task_id==tid))).scalar_one_or_none()
            if not st: return None
            result = {"id":st.id,"role":st.role,"description":st.description,"status":st.status,"depends_on":st.depends_on,"duration":st.duration,"error_msg":st.error_msg}
            if st.output_summary:
                try: result["output_summary"] = json.loads(st.output_summary)
                except: result["output_summary"] = st.output_summary
            return result

    async def list_tasks(self, limit=50, offset=0):
        async with self.db() as s:
            from app.models.task import Task; from sqlalchemy import select
            return [{"id":t.id,"user_input":t.user_input,"status":t.status,"zip_url":t.zip_url,"created_at":t.created_at.isoformat() if t.created_at else None,"finished_at":t.finished_at.isoformat() if t.finished_at else None} for t in (await s.execute(select(Task).order_by(Task.created_at.desc()).offset(offset).limit(limit))).scalars().all()]

    async def enqueue_task(self, tid, inp, code_content: str = ""):
        self._pending += 1; pos = self._pending
        await self._queue.put((tid, inp, code_content))
        await self._emit("task_queued",{"task_id":tid,"queue_position":pos,"status":"queued"})
        await self._chat("leader",f"任务已排队，队列中第 {pos}")
        if self._qw is None or self._qw.done(): self._qw = asyncio.create_task(self._qw_worker())
        return pos

    async def _qw_worker(self):
        while True:
            item = await self._queue.get()
            if len(item) >= 2:
                tid, inp = item[0], item[1]
                code_content = item[2] if len(item) > 2 else ""
            else:
                tid, inp = item, ""; code_content = ""
            try:
                await self._emit("task_update",{"task_id":tid,"status":"running"})
                async with self._lock:
                    try:
                        self._current_task = asyncio.create_task(self._run(tid, inp, code_content))
                        await asyncio.wait_for(self._current_task, timeout=300)
                    except asyncio.TimeoutError:
                        logger.error(f"Task {tid} timed out (300s)")
                        await self._emit("task_update",{"task_id":tid,"status":"failed","error":"timeout"})
                        await self._chat("leader",f"Task {tid} timed out")
                    except asyncio.CancelledError:
                        # _run 内部已处理 cancelled 状态，这里无需额外操作
                        logger.info(f"Task {tid} was cancelled")
            except asyncio.CancelledError:
                logger.info(f"Queue worker cancelled for task {tid}")
            except Exception as e:
                logger.error(f"Task {tid} failed: {e}"); await self._emit("task_update",{"task_id":tid,"status":"failed","error":str(e)})
            finally: self._pending -= 1; self._queue.task_done(); self._current_task = None

    async def _save_ck(self, tid, phase, data):
        try:
            async with self.db() as s:
                from app.models.task import Task
                t = await s.get(Task, tid)
                if t: t.checkpoint_data = json.dumps({"phase":phase,"data":data,"ts":datetime.utcnow().isoformat()},ensure_ascii=False); await s.commit()
        except Exception as e: logger.warning(f"Checkpoint save 失败: {e}")

    async def _run(self, tid, inp, code_content: str = ""):
        self._cancel.clear(); self._paused = False; self._pause_ev = None; self._iv_events = {}; self._iv_results = {}
        try:
            await self._update_status(tid,"running"); await self._emit("task_update",{"task_id":tid,"status":"running"})
            self._check_cancel(); await self._check_pause()

            # --- 新流程：Leader 分析代码 → 生成测试任务队列 ---
            lcfg = await self._get_config("leader")
            leader = LeaderAgent(lcfg); leader.set_status_callback(lambda d: self._emit("worker_status",{"worker_id":"leader",**d}))
            leader.set_stream_callback(lambda t: asyncio.ensure_future(self._emit("stream_token",{"worker_id":"leader","token":t})))

            # 如果有代码内容，走代码分析流程；否则回退到旧流程
            if code_content:
                code_to_analyze = code_content
                user_supplement = inp  # 用户补充说明
                dec = await leader.decompose(code_to_analyze, user_supplement)
                await self._chat("leader",f"代码分析完成：发现了 {dec.get('ast_analysis', {}).get('function_count', 0)} 个函数，生成 {len(dec.get('subtasks', []))} 个测试子任务")
            else:
                # 无代码内容时的后备（兼容旧输入模式）
                dec = await leader.decompose(inp)
                code_to_analyze = ""

            subs = dec.get("subtasks", []); self._check_cancel()
            if not subs:
                logger.warning("没有生成任何子任务，直接生成汇总报告")
                await self._chat("leader", "代码分析完成，但未生成测试子任务（代码过于简单或 LLM 未返回有效任务）")
                summary = await leader.generate_summary(user_input=inp, code_content=code_to_analyze, ast_analysis=dec.get("ast_analysis"))
                await self._update_status(tid, "done")
                await self._emit("task_update", {"task_id": tid, "status": "done"})
                await self._chat("leader", summary, phase="summary")
                return
            await self._chat("leader", f"已生成 {len(subs)} 个子任务，开始并行执行...")
            await self._save_subs(tid, subs)
            for s in subs:
                sid = s.get("db_id", s["id"])
                dep_raw = s.get("depends_on")
                dep_prefixed = f"{tid}_{dep_raw}" if dep_raw and not str(dep_raw).startswith(f"{tid}_") else dep_raw
                await self._emit("subtask_update",{"task_id":tid,"subtask_id":sid,"status":"pending","role":s["role"],"description":s.get("description",""),"depends_on":dep_prefixed})
                await asyncio.sleep(0.5)
            await self._save_ck(tid,"decomposed",{"subtasks":subs})
            self._check_cancel(); await self._check_pause()

            # 构建 DAG 任务定义
            test_results = {}
            rdescs = {}; tdefs = []
            function_codes = {}  # 保存每个函数的代码片段
            functions_info = dec.get("functions", [])
            code_content_map = {}  # function_name -> function_code

            # 从代码中提取每个函数的代码
            if code_to_analyze and functions_info:
                for func_info in functions_info:
                    func_name = func_info.get("name", "")
                    # 简单的代码提取：通过函数名在源代码中定位
                    import re
                    pattern = rf"def\s+{re.escape(func_name)}\s*\(.*?\):"
                    match = re.search(pattern, code_to_analyze)
                    if match:
                        # 提取从 def 到下一个 def/class/文件末尾
                        start = match.start()
                        rest = code_to_analyze[start:]
                        # 找下一个 def 或 class
                        next_def = re.search(r"\n(?=def\s+|class\s+)", rest[1:])
                        if next_def:
                            end = next_def.start() + 1
                        else:
                            end = len(rest)
                        function_codes[func_name] = rest[:end].strip()

            for s in subs:
                d = s.get("depends_on")
                deps = [d] if isinstance(d, str) and d.strip() else (d if isinstance(d, list) else [])
                sid = s.get("db_id", s["id"])
                deps = [f"{tid}_{dep}" if dep and not dep.startswith(f"{tid}_") else dep for dep in deps]
                tdefs.append(TaskDef(id=sid, role=s["role"], description=s.get("description", ""), depends_on=deps))
                rdescs[s["role"]] = s.get("description", "")

            # 收集所有 tester 和 coder 角色的任务用于汇总
            all_coder_results = []
            pm_input_data = {}

            async def coder_ex(td, ctx):
                """为单个函数编写单元测试（每个coder子任务对应一个函数的测试）"""
                nonlocal test_results, all_coder_results
                desc = rdescs.get("coder", td.description)
                self._check_cancel(); await self._check_pause()
                t0 = time.time()

                # 从任务描述中提取函数名
                func_name = ""
                for task_s in subs:
                    if task_s.get("db_id", task_s["id"]) == td.id:
                        func_name = task_s.get("function_name", "")
                        break

                func_code = function_codes.get(func_name, code_to_analyze)
                func_info = next((f for f in functions_info if f["name"] == func_name), {})
                signature = func_info.get("signature", f"{func_name}(...)")
                dependencies = [c for c in func_info.get("calls", []) if c]

                await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "status": "running", "input": f"为 {func_name} 编写测试", "phase": "connecting_llm"})
                await self._emit("worker_status", {"worker_id": "coder", "status": "running", "phase": f"writing_tests:{func_name}"})
                await self._chat("coder", f"开始为函数 {func_name} 编写测试...")

                try:
                    r = await self._run_coder_for_function(tid, func_code, func_name, signature, dependencies)
                except Exception as e:
                    logger.error(f"Coder task for {func_name} failed: {e}")
                    r = {"files": {}, "summary": f"测试生成失败: {e}", "test_scenarios": []}

                dur = time.time() - t0
                if r and r.get("files", {}):
                    await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "phase": "completed", "files": list(r["files"].keys())})
                else:
                    await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "phase": "completed", "files": []})

                await self._chat("coder", f"{func_name} 测试编写完成，场景: {r.get('test_scenarios', [])}")
                await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "status": "done", "duration": dur, "output": r.get("summary", "")})
                await self._emit("worker_status", {"worker_id": "coder", "status": "done", "duration": dur})
                await self._save_subtask_result(tid, td.id, r, dur)

                all_coder_results.append(r)
                test_results[td.id] = r
                return r

            async def pm_ex(td, ctx):
                """审核所有测试代码质量"""
                nonlocal test_results
                self._check_cancel(); await self._check_pause()
                # 放宽条件：如果 coder 还没跑完但 PM 被调度了，等待片刻再检查
                if not all_coder_results:
                    logger.info("PM 执行时 all_coder_results 为空，等待 coder 完成...")
                    await asyncio.sleep(1)
                if not all_coder_results:
                    return {"score": 0, "summary": "No test code generated", "decision": "escalate"}

                t0 = time.time()
                await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "status": "running", "phase": "reviewing"})
                await self._emit("worker_status", {"worker_id": "pm", "status": "running", "phase": "reviewing"})
                await self._chat("pm", "正在审核所有测试代码...")

                # 收集所有测试代码和被测源代码
                all_test_code = ""
                all_source_code = code_to_analyze
                for r in all_coder_results:
                    for fn, fc in r.get("files", {}).items():
                        all_test_code += f"\n# --- {fn} ---\n{fc}\n"

                # 如果有tester执行结果，也带上
                pytest_output = ""
                coverage_str = ""
                for tid_key, tr in test_results.items():
                    if isinstance(tr, dict):
                        pytest_output = tr.get("sandbox_output", "") or tr.get("output", "")
                        coverage_detail = tr.get("coverage_detail", {})
                        if coverage_detail:
                            coverage_str = json.dumps(coverage_detail, ensure_ascii=False)

                r = await self._run_pm_scoring(all_test_code, all_source_code, pytest_output, coverage_str)
                sc = r.get("score", 0)

                dur = time.time() - t0
                await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "phase": "completed"})
                await self._emit("worker_status", {"worker_id": "pm", "phase": "completed"})
                await self._chat("pm", f"测试代码审核: {sc}/100, {r.get('summary', '')}")
                await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "status": "done", "duration": dur, "output": r.get("summary", ""), "score": sc})
                await self._emit("worker_status", {"worker_id": "pm", "status": "done", "duration": dur})
                await self._save_subtask_result(tid, td.id, r, dur)
                test_results[td.id] = r
                return r

            async def tester_ex(td, ctx):
                """执行所有测试并收集覆盖率"""
                nonlocal test_results
                self._check_cancel(); await self._check_pause()
                if not all_coder_results:
                    return {"status": "failed", "summary": "No tests to run"}

                t0 = time.time()
                await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "status": "running", "phase": "running_tests"})
                await self._emit("worker_status", {"worker_id": "tester", "status": "running", "phase": "running_tests"})
                await self._chat("tester", "正在执行所有测试...")

                # 收集所有测试文件 + 被测代码文件
                all_files = {}
                if code_to_analyze:
                    all_files["source_code.py"] = code_to_analyze
                for r in all_coder_results:
                    for fn, fc in r.get("files", {}).items():
                        all_files[fn] = fc

                r = await self._run_tester_exec(tid, all_files, code_to_analyze)

                dur = time.time() - t0
                coverage_pct = r.get("coverage_pct", 0)
                test_counts = r.get("test_counts", {})
                await self._chat("tester", f"测试完成: 通过 {test_counts.get('passed', 0)}/{sum(test_counts.values()) or 1}, 覆盖率 {coverage_pct:.1f}%")
                await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "phase": "completed"})
                await self._emit("worker_status", {"worker_id": "tester", "phase": "completed"})
                await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "status": "done", "duration": dur, "output": r.get("summary", {}).get("summary", "")})
                await self._emit("worker_status", {"worker_id": "tester", "status": "done", "duration": dur})
                await self._save_subtask_result(tid, td.id, r, dur)
                test_results[td.id] = r
                return r

            emap = {"coder": coder_ex, "pm": pm_ex, "tester": tester_ex}
            dag = DAGTaskExecutor()
            dag.set_checkpoint_callback(lambda cd: self._save_ck(tid, "dag", cd))
            dag.set_status_callback(lambda d: self._emit("worker_status", {"worker_id": d.get("role", ""), **d}))
            drs = await dag.execute(tdefs, emap, {"task_id": tid})

            # ── 强制清理：标记 DAG 中仍为 running/pending 的子任务为 done ──
            for td in tdefs:
                if td.status in ("running", "pending"):
                    logger.warning(f"Force-completing stuck subtask {td.id} ({td.role})")
                    await self._emit("subtask_update", {"task_id": tid, "subtask_id": td.id, "status": "done", "duration": 0, "output": "自动完成（超时或异常）"})
                    await self._emit("worker_status", {"worker_id": td.role, "status": "done"})

            # 汇总结果
            # 收集覆盖率数据
            coverage_data = {}
            for tid_key, tr in test_results.items():
                if isinstance(tr, dict):
                    if tr.get("coverage_detail"):
                        coverage_data = tr["coverage_detail"]
                    elif tr.get("coverage_pct"):
                        coverage_data = {"line_rate": tr["coverage_pct"] / 100.0}

            # 收集PM结果
            pm_final = {}
            coder_final_list = []
            for tid_key, tr in test_results.items():
                if isinstance(tr, dict):
                    if "test_scenarios" in tr:
                        coder_final_list.append(tr)
                    if "hard_score" in tr or "score" in tr:
                        pm_final = tr

            # 合并 coder 结果
            coder_final = {"files": {}, "summary": "", "test_scenarios": []}
            for r in coder_final_list:
                if r.get("files"):
                    coder_final["files"].update(r["files"])
                if r.get("summary"):
                    coder_final["summary"] += ("; " if coder_final["summary"] else "") + r["summary"]
                if r.get("test_scenarios"):
                    coder_final["test_scenarios"].extend(r["test_scenarios"])

            # 生成最终报告
            summary = await leader.generate_summary(
                user_input=inp,
                code_content=code_to_analyze,
                coder_result=coder_final,
                pm_result=pm_final,
                tester_result=test_results.get("TEST_EXEC", {}),
                coverage_data=coverage_data,
                ast_analysis=dec.get("ast_analysis"),
            )

            has_output = bool(coder_final.get("files", {}))
            if has_output:
                zp = await self.fs.create_zip(tid)
                zu = f"/api/tasks/{tid}/download"
                await self._update_status(tid, "done", zip_url=zp)
            else:
                zu = None
                await self._update_status(tid, "done")
            await self._emit("task_update", {"task_id": tid, "status": "done", "zip_url": zu})
            await self._chat("leader", summary, phase="summary", zip_url=zu)

            # Auto-inject into RAG knowledge base
            if self.rag_service and hasattr(self.rag_service, 'add_task_result'):
                try:
                    rag_subtasks = []
                    for s in subs:
                        sid = s["id"]
                        result = drs.get(sid, {})
                        rag_subtasks.append({
                            "description": s.get("description", ""),
                            "role": s.get("role", ""),
                            "output_summary": json.dumps({
                                "summary": result.get("summary", ""),
                                "files": list(result.get("files", {}).keys()) if isinstance(result.get("files"), dict) else (result.get("files") or []),
                                "score": result.get("score"),
                                "issues": result.get("issues", []),
                            }, ensure_ascii=False),
                        })
                    task_data = {"id": tid, "user_input": inp, "subtasks": rag_subtasks}
                    self.rag_service.add_task_result(task_data)
                except Exception as e:
                    logger.warning(f"RAG auto-inject for task {tid} failed: {e}")

        except asyncio.CancelledError:
            await self._update_status(tid,"cancelled"); await self._emit("task_update",{"task_id":tid,"status":"cancelled"}); await self._chat("leader","Task cancelled")
        except Exception as e:
            if self._cancel and self._cancel.is_set():
                await self._update_status(tid,"cancelled"); await self._emit("task_update",{"task_id":tid,"status":"cancelled"}); await self._chat("leader","Task cancelled")
            else:
                logger.error(f"Task {tid} 失败: {e}"); await self._update_status(tid,"failed",error_msg=str(e)); await self._emit("task_update",{"task_id":tid,"status":"failed","error":str(e)}); await self._chat("leader",f"Task 失败: {str(e)}")

    async def _run_coder_for_function(self, tid, func_code, func_name, signature, dependencies):
        """为单个函数编写单元测试（超时 90s）"""
        cfg = await self._get_config("coder")
        c = CoderWorker(cfg); c.set_status_callback(lambda d: self._emit("worker_status",{"worker_id":"coder",**d}))
        c.set_stream_callback(lambda t: asyncio.ensure_future(self._emit("stream_token",{"worker_id":"coder","token":t})))
        try:
            r = await asyncio.wait_for(
                c.write_tests(func_code, func_name, signature, dependencies),
                timeout=90,
            )
        except asyncio.TimeoutError:
            logger.error(f"Coder timeout for {func_name} (90s)")
            r = {"files": {}, "summary": f"函数 {func_name} 测试生成超时", "test_scenarios": [], "language": "Python"}
        for fn,fc in r.get("files", {}).items(): await self.fs.save_file("coder",fn,fc,task_id=tid)
        await self._emit("stream_token",{"worker_id":"coder","isFinal":True})
        return r

    async def _run_pm_scoring(self, test_code, source_code, pytest_output="", coverage_report=""):
        """审核测试代码质量（超时 60s）"""
        if not test_code.strip():
            return {"score": 0, "hard_score": 0, "soft_score": 0, "decision": "escalate", "summary": "No test code"}
        cfg = await self._get_config("pm")
        p = PMWorker(cfg); p.set_status_callback(lambda d: self._emit("worker_status",{"worker_id":"pm",**d}))
        p.set_stream_callback(lambda t: asyncio.ensure_future(self._emit("stream_token",{"worker_id":"pm","token":t})))
        try:
            r = await asyncio.wait_for(
                p.review_code(test_code, source_code, pytest_output, coverage_report),
                timeout=60,
            )
        except asyncio.TimeoutError:
            logger.error("PM review timed out (60s)")
            r = {"score": 60, "hard_score": 40, "soft_score": 20, "decision": "pass_with_warning", "summary": "PM 审核超时，自动放行", "issues": ["审核超时，请人工复查"], "pass": True}
        await self._chat("pm", f"PM审核: {r.get('score', 0)}/100 (硬指标:{r.get('hard_score', 0)} 软指标:{r.get('soft_score', 0)}), {r.get('summary', '')}")
        await self._emit("stream_token", {"worker_id": "pm", "isFinal": True})
        return r

    async def _run_tester_exec(self, tid, all_files, source_code=""):
        """执行测试并解析覆盖率（超时 120s）"""
        if not all_files:
            return {"status": "failed", "summary": "No files to test"}
        cfg = await self._get_config("tester")
        t = TesterWorker(cfg); t.set_status_callback(lambda d: self._emit("worker_status",{"worker_id":"tester",**d}))
        t.set_stream_callback(lambda dt: asyncio.ensure_future(self._emit("stream_token",{"worker_id":"tester","token":dt})))
        mc = source_code or next((c for f, c in all_files.items() if f.endswith(".py")), "")
        try:
            r = await asyncio.wait_for(t.write_tests(mc, "Execute all tests"), timeout=120)
        except asyncio.TimeoutError:
            logger.error("Tester task timed out (120s)")
            r = {"test_files": {}, "test_command": "", "summary": "测试执行超时"}
        for fn, fc in r.get("test_files", {}).items():
            await self.fs.save_file("tester", fn, fc, task_id=tid)
            all_files[fn] = fc
        await self._emit("stream_token", {"worker_id": "tester", "isFinal": True})
        try:
            sandbox_result = await self.ss.run_tests(all_files)
            r["sandbox_output"] = sandbox_result
            # 解析测试结果
            test_result = t.parse_test_results(sandbox_result)
            r.update(test_result)
        except Exception as e:
            logger.warning(f"Test execution failed: {e}")
            r["sandbox_output"] = f"Error: {e}"
            r["coverage_pct"] = 0.0
            r["coverage_detail"] = {"line_rate": 0.0, "grade": "unknown"}
            r["test_counts"] = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
        return r
    async def _update_status(self, tid, status, **kw):
        async with self.db() as s:
            from app.models.task import Task
            t = await s.get(Task, tid)
            if t:
                t.status = status
                if status=="done": t.finished_at = datetime.utcnow()
                for k in ("error_msg","zip_url"):
                    if k in kw: setattr(t,k,kw[k])
                await s.commit()
    async def delete_task(self, tid):
        async with self.db() as s:
            from app.models.task import Task; from app.services.file_service import OUTPUT_BASE_DIR
            t = await s.get(Task, tid)
            if not t: return False
            await s.delete(t); await s.commit()
        import shutil
        try:
            td = self.fs._get_task_dir(tid)
            if os.path.exists(td): shutil.rmtree(td)
            zp = os.path.join(OUTPUT_BASE_DIR, f"{tid}.zip")
            if os.path.exists(zp): os.remove(zp)
        except: pass
        return True
    async def _save_subs(self, tid, subs):
        async with self.db() as s:
            from app.models.task import Subtask
            for i,st in enumerate(subs):
                d = st.get("depends_on")
                if isinstance(d,list): d = ",".join(d) if d else None
                # Prefix with task_id to avoid global UNIQUE conflicts
                raw_id = st.get("id") or generate_subtask_id()
                sid = f"{tid}_{raw_id}"
                # Prefix depends_on reference too
                d_prefixed = f"{tid}_{d}" if d and not str(d).startswith(f"{tid}_") else d
                st["db_id"] = sid  # Store for later use by DAG executor / SSE emits
                s.add(Subtask(id=sid, task_id=tid, role=st["role"], description=st.get("description",""), depends_on=d_prefixed, sort_order=i, status="pending"))
            await s.commit()

    async def _save_subtask_result(self, tid, subtask_id: str, result: dict, duration: float):
        """Persist subtask execution result to DB"""
        try:
            async with self.db() as s:
                from app.models.task import Subtask
                st = await s.get(Subtask, subtask_id)
                if st:
                    st.status = "done" if result.get("status") != "failed" else "failed"
                    st.duration = int(duration)
                    st.output_summary = json.dumps({
                        "summary": result.get("summary", ""),
                        "files": list(result.get("files", {}).keys()) if result.get("files") else [],
                        "score": result.get("score"),
                        "issues": result.get("issues", []),
                    }, ensure_ascii=False)
                    st.error_msg = result.get("error", "")
                    await s.commit()
        except Exception as e:
            logger.warning(f"Save subtask result failed: {e}")