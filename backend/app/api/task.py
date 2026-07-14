"""Task API routes - 支持代码文件上传、测试任务管理"""
import logging, os, traceback, json
from fastapi import APIRouter, HTTPException, Depends, Body, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from app.services.task_service import TaskService
from app.services.file_service import OUTPUT_BASE_DIR
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# ── 原始 Request 模型（保持兼容）──
class TaskCreateRequest(BaseModel):
    user_input: str

class TaskCreateWithCodeRequest(BaseModel):
    user_input: str = ""
    code_content: str = ""

class InterventionRequest(BaseModel):
    request_id: str; decision: str; feedback: str = ""

def get_ts(): from app.main import app_state; return app_state.task_service


@router.post("/create")
async def create_task(req: TaskCreateRequest, ts: TaskService = Depends(get_ts)):
    """[原始接口] 创建任务（纯文本需求）"""
    if not req.user_input or not req.user_input.strip():
        raise HTTPException(400, "Input required")
    tid = await ts.create_task_record(req.user_input.strip())
    pos = await ts.enqueue_task(tid, req.user_input.strip())
    return {"task_id": tid, "status": "queued", "queue_position": pos}


@router.post("/create-with-code")
async def create_task_with_code(req: TaskCreateWithCodeRequest, ts: TaskService = Depends(get_ts)):
    """[新接口] 创建任务（支持代码内容+文本说明）"""
    if not req.user_input and not req.code_content:
        raise HTTPException(400, "请提供代码内容或输入说明")
    input_text = req.user_input or "测试代码"
    tid = await ts.create_task_record(input_text, req.code_content)
    pos = await ts.enqueue_task(tid, input_text, req.code_content)
    return {"task_id": tid, "status": "queued", "queue_position": pos, "code_uploaded": bool(req.code_content)}


@router.post("/upload")
async def upload_code(
    file: UploadFile = File(...),
    supplement: str = Form(""),
    ts: TaskService = Depends(get_ts),
):
    """[新接口] 上传代码文件并创建测试任务"""
    allowed_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(400, f"不支持的文件类型: {ext}，支持: {', '.join(allowed_extensions)}")

    try:
        content = await file.read()
        code_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "文件编码必须为 UTF-8")
    except Exception as e:
        raise HTTPException(400, f"文件读取失败: {e}")

    if not code_content.strip():
        raise HTTPException(400, "文件内容为空")

    input_text = supplement or f"测试文件: {file.filename}"
    tid = await ts.create_task_record(input_text, code_content)
    pos = await ts.enqueue_task(tid, input_text, code_content)

    return {
        "task_id": tid,
        "status": "queued",
        "queue_position": pos,
        "filename": file.filename,
        "code_length": len(code_content),
        "code_uploaded": True,
    }


@router.post("/upload/text")
async def upload_code_text(
    data: dict = Body(...),
    ts: TaskService = Depends(get_ts),
):
    """[新接口] 接收代码文本（前端编辑器粘贴代码）"""
    code_content = data.get("code", "")
    supplement = data.get("supplement", "")
    filename = data.get("filename", "code.py")

    if not code_content.strip():
        raise HTTPException(400, "代码内容为空")

    input_text = supplement or f"测试文件: {filename}"
    tid = await ts.create_task_record(input_text, code_content)
    pos = await ts.enqueue_task(tid, input_text, code_content)

    return {
        "task_id": tid,
        "status": "queued",
        "queue_position": pos,
        "filename": filename,
        "code_length": len(code_content),
        "code_uploaded": True,
    }


# ── 以下为原始接口，不做改动 ──

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

@router.get("/{tid}/subtasks/{subtask_id}")
async def get_subtask_detail(tid: str, subtask_id: str, ts: TaskService = Depends(get_ts)):
    detail = await ts.get_subtask_detail(tid, subtask_id)
    if not detail:
        raise HTTPException(404, "Subtask not found")
    return detail

@router.get("/{tid}/files")
async def list_files(tid: str, ts: TaskService = Depends(get_ts)):
    return {"files": ts.fs.list_task_files(tid)}

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
