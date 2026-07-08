"""DAG parallel task executor"""
import asyncio, logging
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from app.config import PARALLEL_MAX_WORKERS
logger = logging.getLogger(__name__)
@dataclass
class TaskDef:
    id: str; role: str; description: str; depends_on: List[str] = field(default_factory=list)
    status: str = "pending"; result: Any = None; error: Optional[str] = None

class DAGTaskExecutor:
    def __init__(self, mw=None):
        self.max_workers=mw or PARALLEL_MAX_WORKERS; self._semaphore=None; self._task_map={}
        self._completed=set(); self._failed=set(); self._results={}; self._checkpoint_cb=None; self._status_cb=None
    def set_checkpoint_callback(self,cb): self._checkpoint_cb=cb
    def set_status_callback(self,cb): self._status_cb=cb
    def _sort(self):
        deg={t:len(d.depends_on) for t,d in self._task_map.items()}; rem=set(self._task_map.keys()); lvls=[]
        while rem:
            cur=[t for t in rem if deg[t]==0]
            if not cur: lvls.append(list(rem)); break
            lvls.append(cur)
            for t in cur:
                rem.remove(t)
                for t2,d2 in self._task_map.items():
                    if t2 in rem and t in d2.depends_on: deg[t2]-=1
        return lvls
    async def execute(self, defs, emap, ctx=None):
        self._task_map={t.id:t for t in defs}; self._completed.clear(); self._failed.clear(); self._results.clear()
        self._semaphore=asyncio.Semaphore(self.max_workers)
        for li,lt in enumerate(self._sort()):
            tasks=[]
            for tid in lt:
                t=self._task_map[tid]; ex=emap.get(t.role)
                if not ex: t.status="skipped"; continue
                if [d for d in t.depends_on if d in self._failed]: t.status="skipped"; self._results[t.id]={"skipped":True}; continue
                tasks.append(self._run(t,ex,ctx))
            if tasks: await asyncio.gather(*tasks,return_exceptions=True)
            if self._checkpoint_cb: await self._checkpoint_cb({"level":li,"completed":list(self._completed),"failed":list(self._failed)})
        return self._results
    async def _run(self,t,ex,ctx):
        async with self._semaphore:
            t.status="running"
            if self._status_cb: await self._status_cb({"type":"task_start","task_id":t.id,"role":t.role})
            try:
                r=await ex(t,ctx); t.status="done"; t.result=r; self._completed.add(t.id); self._results[t.id]=r
                if self._status_cb: await self._status_cb({"type":"task_done","task_id":t.id,"role":t.role})
            except asyncio.CancelledError: t.status="failed"; t.error="cancelled"; self._failed.add(t.id); self._results[t.id]={"status":"cancelled"}; raise
            except Exception as e: t.status="failed"; t.error=str(e); self._failed.add(t.id); self._results[t.id]={"status":"failed","error":str(e)}