"""Task API routes with pause/resume/intervention"""
import logging, os, traceback
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.services.task_service import TaskService
from app.services.file_service import OUTPUT_BASE_DIR
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])
class TaskCreateRequest(BaseModel): user_input: str
class InterventionRequest(BaseModel): request_id: str; decision: str; feedback: str = ""
def get_ts(): from app.main import app_state; return app_state.task_service

@router.post("/create")
async def create_task(req: TaskCreateRequest, ts: TaskService = Depends(get_ts)):
    if not req.user_input or not req.user_input.strip(): raise HTTPException(400, "Input required")
    tid = await ts.create_task_record(req.user_input.strip())
    pos = await ts.enqueue_task(tid, req.user_input)
    return {"task_id": tid, "status": "queued", "queue_position": pos}

@router.get("/history")
async def list_tasks(limit: int = 50, offset: int = 0, ts: TaskService = Depends(get_ts)):
    tasks = await ts.list_tasks(limit=limit, offset=offset); return {"tasks": tasks, "total": len(tasks)}

@router.get("/{tid}/download")
async def download(tid: str):
    zp = os.path.join(OUTPUT_BASE_DIR, f"{tid}.zip")
    if not os.path.exists(zp): raise HTTPException(404, "File not found")
    return FileResponse(zp, media_type="application/zip", filename=f"{tid}.zip")

@router.get("/{tid}")
async def get_task(tid: str, ts: TaskService = Depends(get_ts)):
    t = await ts.get_task(tid)
    if not t:
        raise HTTPException(404, "Task not found")
    return t

@router.get("/{tid}/subtasks")
async def get_subtasks(tid: str, ts: TaskService = Depends(get_ts)):
    return {"subtasks": await ts.get_subtasks(tid)}

@router.get("/{tid}/files")
async def list_files(tid: str, ts: TaskService = Depends(get_ts)):
    return {"files": ts.file_service.list_task_files(tid)}

@router.delete("/{tid}")
async def delete_task(tid: str, ts: TaskService = Depends(get_ts)):
    if not await ts.delete_task(tid): raise HTTPException(404, "Not found")
    return {"status": "deleted"}

@router.post("/cancel")
async def cancel(ts: TaskService = Depends(get_ts)):
    ts.cancel_current_task(); return {"status": "cancelled"}

@router.post("/pause")
async def pause(ts: TaskService = Depends(get_ts)):
    await ts.pause_current_task(); return {"status": "paused"}

@router.post("/resume")
async def resume(ts: TaskService = Depends(get_ts)):
    await ts.resume_current_task(); return {"status": "resumed"}

@router.post("/intervention")
async def intervention(req: InterventionRequest, ts: TaskService = Depends(get_ts)):
    await ts.send_intervention(req.request_id, req.decision, req.feedback); return {"status": "received"}

@router.post("/batch/delete")
async def batch_delete(tids: list[str] = Body(...), ts: TaskService = Depends(get_ts)):
    deleted = 0
    for tid in tids:
        if await ts.delete_task(tid): deleted += 1
    return {"deleted_count": deleted, "total": len(tids)}