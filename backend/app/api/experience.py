"""Experience API routes - knowledge accumulation & ratings"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/experience", tags=["experience"])


class SaveExperienceRequest(BaseModel):
    task_id: str
    user_input: str = ""
    summary: str = ""
    rating: int = 0
    tags: str = ""
    notes: str = ""
    task_status: str = ""
    subtask_count: int = 0
    total_duration: float = 0


class RateRequest(BaseModel):
    rating: int
    notes: str = ""


def get_exp():
    from app.main import app_state
    if not app_state.experience_service:
        raise HTTPException(503, "Experience service not available")
    return app_state.experience_service


@router.post("/save")
async def save_experience(req: SaveExperienceRequest, svc=Depends(get_exp)):
    """Save or update experience from a completed task"""
    exp = await svc.save_experience(
        task_id=req.task_id,
        user_input=req.user_input,
        summary=req.summary,
        rating=req.rating,
        tags=req.tags,
        notes=req.notes,
        task_status=req.task_status,
        subtask_count=req.subtask_count,
        total_duration=req.total_duration,
    )
    return exp


# ── Static routes first (before /{param}) ──

@router.get("/stats")
async def experience_stats(svc=Depends(get_exp)):
    """Get experience statistics"""
    return await svc.get_stats()


@router.get("/search")
async def search_experiences(
    q: str = Query("", alias="q"),
    tag: str = "",
    limit: int = 10,
    offset: int = 0,
    svc=Depends(get_exp),
):
    """Search experiences by keyword"""
    return await svc.search_experiences(query=q, tag=tag, limit=limit, offset=offset)


@router.get("/recommended")
async def recommended(limit: int = 5, svc=Depends(get_exp)):
    """Get recommended experiences"""
    return {"results": await svc.get_recommended(limit=limit)}


# ── Param routes ──

@router.get("/{task_id}")
async def get_experience(task_id: str, svc=Depends(get_exp)):
    """Get experience for a specific task"""
    exp = await svc.get_task_experience(task_id)
    if not exp:
        raise HTTPException(404)
    return exp


@router.post("/{exp_id}/rate")
async def rate_experience(exp_id: str, req: RateRequest, svc=Depends(get_exp)):
    """Rate an experience"""
    result = await svc.rate_experience(exp_id, req.rating, req.notes)
    if not result:
        raise HTTPException(404)
    return result


@router.post("/{exp_id}/reuse")
async def reuse_experience(exp_id: str, svc=Depends(get_exp)):
    """Increment reuse count (implicit feedback)"""
    result = await svc.increment_reuse(exp_id)
    if not result:
        raise HTTPException(404)
    return result


@router.delete("/{exp_id}")
async def delete_experience(exp_id: str, svc=Depends(get_exp)):
    """Delete an experience"""
    ok = await svc.delete_experience(exp_id)
    if not ok:
        raise HTTPException(404)
    return {"status": "deleted"}
