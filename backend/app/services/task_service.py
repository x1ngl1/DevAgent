"""Task service - DAG parallel + streaming + checkpoint"""
import asyncio, json, logging, os, traceback
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
from app.utils.tool_registry import register_builtin_tools, ToolRegistry
logger = logging.getLogger(__name__)
class TaskService:
    def __init__(self, dbf, wcs):
        self.db = dbf; self.wcs = wcs; self._sse_cb = None
        self._queue = asyncio.Queue(); self._lock = asyncio.Lock(); self._qw = None; self._pending = 0
        self.fs = FileService(); self.ss = SandboxService(); self.cs = None
        self._cancel = None; self._current_task = None; self.stream = StreamService()
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
    async def create_task_record(self, inp):
        from app.models.database import async_session_factory
        from app.models.task import Task
        tid = f"T{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(2).hex().upper()}"
        async with async_session_factory() as s: s.add(Task(id=tid, user_input=inp, status="pending")); await s.commit()
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
            return [{"id":st.id,"role":st.role,"description":st.description,"status":st.status,"output_summary":st.output_summary,"error_msg":st.error_msg,"duration":st.duration} for st in sts]

    async def list_tasks(self, limit=50, offset=0):
        async with self.db() as s:
            from app.models.task import Task; from sqlalchemy import select
            return [{"id":t.id,"user_input":t.user_input,"status":t.status,"zip_url":t.zip_url,"created_at":t.created_at.isoformat() if t.created_at else None,"finished_at":t.finished_at.isoformat() if t.finished_at else None} for t in (await s.execute(select(Task).order_by(Task.created_at.desc()).offset(offset).limit(limit))).scalars().all()]

    async def enqueue_task(self, tid, inp):
        self._pending += 1; pos = self._pending
        await self._queue.put((tid,inp))
        await self._emit("task_queued",{"task_id":tid,"queue_position":pos,"status":"queued"})
        await self._chat("leader",f"任务已排队，队列中第 {pos}")
        if self._qw is None or self._qw.done(): self._qw = asyncio.create_task(self._qw_worker())
        return pos

    async def _qw_worker(self):
        while True:
            tid, inp = await self._queue.get()
            self._current_task = None
            try:
                await self._emit("task_update",{"task_id":tid,"status":"running"})
                async with self._lock:
                    try:
                        self._current_task = asyncio.create_task(self._run(tid, inp))
                        await asyncio.wait_for(self._current_task, timeout=300)
                    except asyncio.TimeoutError:
                        logger.error(f"Task {tid} timed out (300s)")
                        await self._emit("task_update",{"task_id":tid,"status":"failed","error":"timeout"})
                        await self._chat("leader",f"Task {tid} timed out")
            except Exception as e:
                logger.error(f"Task {tid} failed: {e}"); await self._emit("task_update",{"task_id":tid,"status":"failed","error":str(e)})
            finally: self._pending -= 1; self._queue.task_done()

    async def _save_ck(self, tid, phase, data):
        try:
            async with self.db() as s:
                from app.models.task import Task
                t = await s.get(Task, tid)
                if t: t.checkpoint_data = json.dumps({"phase":phase,"data":data,"ts":datetime.utcnow().isoformat()},ensure_ascii=False); await s.commit()
        except Exception as e: logger.warning(f"Checkpoint save 失败: {e}")

    async def _run(self, tid, inp):
        self._cancel = asyncio.Event(); self._paused = False; self._pause_ev = None; self._iv_events = {}; self._iv_results = {}
        try:
            await self._update_status(tid,"running"); await self._emit("task_update",{"task_id":tid,"status":"running"})
            self._check_cancel(); await self._check_pause()
            lcfg = await self._get_config("leader")
            leader = LeaderAgent(lcfg); leader.set_status_callback(lambda d: self._emit("worker_status",{"worker_id":"leader",**d}))
            dec = await leader.decompose(inp); subs = dec.get("subtasks",[]); self._check_cancel()
            await self._chat("leader",f"Decomposed into {len(subs)} 个子任务，开始并行执行...")
            await self._save_subs(tid, subs)
            for s in subs: await self._emit("subtask_update",{"task_id":tid,"subtask_id":s["id"],"status":"pending","role":s["role"],"description":s.get("description",""),"depends_on":s.get("depends_on")})
            await self._save_ck(tid,"decomposed",{"subtasks":subs})
            self._check_cancel(); await self._check_pause()
            if self.cs:
                await self._chat("leader","召集团队讨论任务方案...",phase="discussion"); await asyncio.sleep(0.15)
                try:
                    dr = await self.cs.team_discuss(inp, subs)
                    await self._chat("leader",f"讨论完成 ({dr['rounds']} rounds), starting execution",phase="discussion")
                except Exception as e: logger.warning(f"Discussion: {e}")
            self._check_cancel(); await self._check_pause()
            cr = None
            rdescs = {}; tdefs = []
            for s in subs:
                d = s.get("depends_on")
                deps = [d] if isinstance(d,str) and d.strip() else (d if isinstance(d,list) else [])
                tdefs.append(TaskDef(id=s["id"],role=s["role"],description=s.get("description",""),depends_on=deps))
                rdescs[s["role"]] = s.get("description","")
            async def coder_ex(td, ctx):
                nonlocal cr; desc = rdescs.get("coder",td.description)
                self._check_cancel(); await self._check_pause()
                await self._emit("subtask_update",{"task_id":tid,"subtask_id":td.id,"status":"running"}); await self._chat("coder","开始编写代码...")
                cr = await self._run_coder(tid, desc)
                await self._chat("coder",f"代码编写完成，共 {len(cr.get('files', {}))} 个文件"); await self._emit("subtask_update",{"task_id":tid,"subtask_id":td.id,"status":"done"})
                return cr
            async def pm_ex(td, ctx):
                nonlocal cr; MAX = 3
                self._check_cancel(); await self._check_pause()
                if not cr: return {"score":0,"summary":"No code"}
                await self._emit("subtask_update",{"task_id":tid,"subtask_id":td.id,"status":"running"}); await self._chat("pm","Reviewing code...")
                r = await self._run_pm(cr); sc = r.get("score",0); rt = 1
                while sc < 60 and rt < MAX and cr and cr.get("files", {}):
                    self._check_cancel(); await self._check_pause()
                    await self._chat("pm",f"评分 {sc}/100（<60），修改（第{rt}/{MAX})")
                    d = rdescs.get("coder",td.description) + f"\n[PM #{rt}] Score:{sc}\n{r.get('summary','')}"
                    cr = await self._run_coder(tid, d); r = await self._run_pm(cr); sc = r.get("score",0); rt += 1
                if not cr or not cr.get("files", {}): return {"score":0,"summary":"No code"}
                await self._chat("pm",f"Review {'passed' if sc>=60 else '失败'}: {sc}/100")
                await self._emit("subtask_update",{"task_id":tid,"subtask_id":td.id,"status":"done"}); return r
            async def tester_ex(td, ctx):
                nonlocal cr
                self._check_cancel(); await self._check_pause()
                if not cr or not cr.get("files", {}): return {"status":"failed","summary":"No code"}
                await self._emit("subtask_update",{"task_id":tid,"subtask_id":td.id,"status":"running"}); await self._chat("tester","Writing tests...")
                r = await self._run_tester(tid, rdescs.get("tester",td.description), cr)
                await self._chat("tester","Tests done"); await self._emit("subtask_update",{"task_id":tid,"subtask_id":td.id,"status":"done"}); return r
            emap = {"coder":coder_ex,"pm":pm_ex,"tester":tester_ex}
            dag = DAGTaskExecutor()
            dag.set_checkpoint_callback(lambda cd: self._save_ck(tid,"dag",cd))
            dag.set_status_callback(lambda d: self._emit("worker_status",{"worker_id":d.get("role",""),**d}))
            drs = await dag.execute(tdefs, emap, {"task_id":tid})
            cid = next((s.id for s in tdefs if s.role=="coder"),None)
            pid = next((s.id for s in tdefs if s.role=="pm"),None)
            tid2 = next((s.id for s in tdefs if s.role=="tester"),None)
            cr = drs.get(cid) if cid else cr
            pr = drs.get(pid) if pid else {}
            tr = drs.get(tid2) if tid2 else {}
            summary = await leader.generate_summary(inp, cr, pr, tr)
            has_output = bool(cr and cr.get("files", {}))
            if has_output:
                zp = await self.fs.create_zip(tid); zu = f"/api/tasks/{tid}/download"
                await self._update_status(tid,"done",zip_url=zp)
            else:
                zu = None
                await self._update_status(tid,"done")
            await self._emit("task_update",{"task_id":tid,"status":"done","zip_url":zu})
            await self._chat("leader",summary,phase="summary",zip_url=zu)
        except asyncio.CancelledError:
            await self._update_status(tid,"cancelled"); await self._emit("task_update",{"task_id":tid,"status":"cancelled"}); await self._chat("leader","Task cancelled")
        except Exception as e:
            if self._cancel and self._cancel.is_set():
                await self._update_status(tid,"cancelled"); await self._emit("task_update",{"task_id":tid,"status":"cancelled"}); await self._chat("leader","Task cancelled")
            else:
                logger.error(f"Task {tid} 失败: {e}"); await self._update_status(tid,"失败",error_msg=str(e))
            await self._emit("task_update",{"task_id":tid,"status":"failed","error":str(e)}); await self._chat("leader",f"Task 失败: {str(e)}")

    async def _run_coder(self, tid, desc):
        cfg = await self._get_config("coder")
        c = CoderWorker(cfg); c.set_status_callback(lambda d: self._emit("worker_status",{"worker_id":"coder",**d}))
        r = await c.write_code(desc)
        for fn,fc in r.get("files", {}).items(): await self.fs.save_file("coder",fn,fc,task_id=tid)
        return r
    async def _run_pm(self, cr):
        if not cr: return {"score":0,"summary":"No code"}
        cfg = await self._get_config("pm")
        p = PMWorker(cfg); p.set_status_callback(lambda d: self._emit("worker_status",{"worker_id":"pm",**d}))
        # 将所有产出文件（除README.md外）合并发送给PM，避免PM因只看到部分文件而误判
        all_files = {f:c for f,c in cr.get("files", {}).items() if f!="README.md"}
        if not all_files: return {"score":0,"summary":"No code file"}
        # 将所有文件用文件名标注拼接，让PM看到完整交付物，避免误判"缺少文件"
        mc_parts = []
        for fname, fcontent in all_files.items():
            mc_parts.append(f"【{fname}】\n{fcontent}")
        mc = "\n\n".join(mc_parts)
        language = cr.get("language","Python")
        r = await p.review_code(mc, language)
        await self._chat("pm",f"PM审核: {r.get('score',0)}/100, {r.get('summary','')}"); return r
    async def _run_tester(self, tid, desc, cr):
        if not cr or not cr.get("files", {}): return {"status":"failed","summary":"No code"}
        cfg = await self._get_config("tester")
        t = TesterWorker(cfg); t.set_status_callback(lambda d: self._emit("worker_status",{"worker_id":"tester",**d}))
        mc = next((c for f,c in cr.get("files", {}).items() if f!="README.md"),"")
        r = await t.write_tests(mc, desc)
        for fn,fc in r.get("test_files", {}).items(): await self.fs.save_file("tester",fn,fc,task_id=tid)
        try:
            af = {**cr.get("files", {})}; af.update(r.get("test_files", {}))
            r["sandbox_output"] = await self.ss.run_tests(af)
        except Exception as e: r["sandbox_output"] = f"Sandbox: {e}"
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
                s.add(Subtask(task_id=tid,role=st["role"],description=st.get("description",""),depends_on=d,sort_order=i,status="pending"))
            await s.commit()