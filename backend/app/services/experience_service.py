"""Experience Service - knowledge/experience accumulation from task results"""
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import select, desc, or_, func, and_

from app.models.experience import Experience

logger = logging.getLogger(__name__)


class ExperienceService:
    def __init__(self, db_factory):
        self.db = db_factory

    async def save_experience(
        self,
        task_id: str,
        user_input: str = "",
        summary: str = "",
        rating: int = 0,
        tags: str = "",
        notes: str = "",
        task_status: str = "",
        subtask_count: int = 0,
        total_duration: float = 0,
    ) -> Optional[Experience]:
        """Save or update experience from a task"""
        rating = max(0, min(5, rating))

        async with self.db() as s:
            # Check if experience already exists for this task
            existing = (await s.execute(
                select(Experience).where(Experience.task_id == task_id)
            )).scalar_one_or_none()

            if existing:
                existing.rating = rating if rating > 0 else existing.rating
                existing.tags = tags or existing.tags
                existing.notes = notes or existing.notes
                if tags:
                    existing.tags = tags
                existing.is_recommended = existing.rating >= 4
                existing.is_counterexample = existing.rating <= 1
                existing.updated_at = datetime.utcnow()
                await s.commit()
                await s.refresh(existing)
                return existing

            is_rec = rating >= 4
            is_counter = rating <= 1

            exp = Experience(
                task_id=task_id,
                user_input=user_input,
                summary=summary,
                rating=rating,
                tags=tags,
                notes=notes,
                is_recommended=is_rec,
                is_counterexample=is_counter,
                task_status=task_status or "done",
                subtask_count=subtask_count,
                total_duration=total_duration,
            )
            s.add(exp)
            await s.commit()
            await s.refresh(exp)
            logger.info(f"Experience saved: {exp.id} (rating={rating})")
            return exp

    async def get_task_experience(self, task_id: str) -> Optional[Dict]:
        """Get experience for a specific task"""
        async with self.db() as s:
            exp = (await s.execute(
                select(Experience).where(Experience.task_id == task_id)
            )).scalar_one_or_none()
            return exp.to_dict() if exp else None

    async def search_experiences(
        self,
        query: str = "",
        tag: str = "",
        limit: int = 10,
        offset: int = 0,
    ) -> Dict:
        """Search experiences by keyword + tag matching"""
        async with self.db() as s:
            stmt = select(Experience)

            if query:
                like = f"%{query}%"
                stmt = stmt.where(or_(
                    Experience.user_input.like(like),
                    Experience.summary.like(like),
                    Experience.tags.like(like),
                    Experience.notes.like(like),
                ))

            if tag:
                stmt = stmt.where(Experience.tags.like(f"%{tag}%"))

            # Count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await s.execute(count_stmt)).scalar() or 0

            # Fetch
            stmt = stmt.order_by(desc(Experience.is_recommended), desc(Experience.rating), desc(Experience.created_at))
            stmt = stmt.offset(offset).limit(limit)
            results = (await s.execute(stmt)).scalars().all()

            return {
                "total": total,
                "results": [exp.to_dict() for exp in results],
                "limit": limit,
                "offset": offset,
            }

    async def get_recommended(self, limit: int = 5) -> List[Dict]:
        """Get recommended experiences (rating >= 4)"""
        async with self.db() as s:
            stmt = select(Experience).where(
                Experience.is_recommended == True
            ).order_by(desc(Experience.rating), desc(Experience.reuse_count)).limit(limit)
            results = (await s.execute(stmt)).scalars().all()
            return [exp.to_dict() for exp in results]

    async def rate_experience(self, exp_id: str, rating: int, notes: str = "") -> Optional[Dict]:
        """Rate an experience (update rating + notes)"""
        rating = max(0, min(5, rating))
        async with self.db() as s:
            exp = await s.get(Experience, exp_id)
            if not exp:
                return None
            exp.rating = rating
            exp.is_recommended = rating >= 4
            exp.is_counterexample = rating <= 1
            if notes:
                exp.notes = notes
            exp.updated_at = datetime.utcnow()
            await s.commit()
            await s.refresh(exp)
            return exp.to_dict()

    async def increment_reuse(self, exp_id: str) -> Optional[Dict]:
        """Increment reuse count (implicit feedback)"""
        async with self.db() as s:
            exp = await s.get(Experience, exp_id)
            if not exp:
                return None
            exp.reuse_count = (exp.reuse_count or 0) + 1
            await s.commit()
            await s.refresh(exp)
            return exp.to_dict()

    async def delete_experience(self, exp_id: str) -> bool:
        """Delete an experience"""
        async with self.db() as s:
            exp = await s.get(Experience, exp_id)
            if not exp:
                return False
            await s.delete(exp)
            await s.commit()
            return True

    async def get_stats(self) -> Dict:
        """Get experience statistics"""
        async with self.db() as s:
            total = (await s.execute(select(func.count()).select_from(Experience))).scalar() or 0
            recommended = (await s.execute(
                select(func.count()).where(Experience.is_recommended == True).select_from(Experience)
            )).scalar() or 0
            counter = (await s.execute(
                select(func.count()).where(Experience.is_counterexample == True).select_from(Experience)
            )).scalar() or 0
            avg_rating = (await s.execute(
                select(func.avg(Experience.rating)).where(Experience.rating > 0)
            )).scalar() or 0
            return {
                "total": total,
                "recommended": recommended,
                "counterexamples": counter,
                "avg_rating": round(float(avg_rating), 1),
            }
