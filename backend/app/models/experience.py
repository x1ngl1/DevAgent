"""Experience model - stores task knowledge & user ratings"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


def gen_id():
    return f"EXP{uuid.uuid4().hex[:8].upper()}"


class Experience(Base):
    __tablename__ = "experiences"

    id = Column(String(50), primary_key=True, default=gen_id)
    task_id = Column(String(50), nullable=False, index=True)
    user_input = Column(Text, default="")
    summary = Column(Text, default="")
    rating = Column(Integer, default=0)  # 1-5
    tags = Column(String(500), default="")  # comma-separated
    notes = Column(Text, default="")  # user feedback notes
    is_recommended = Column(Boolean, default=False)  # rating >= 4
    is_counterexample = Column(Boolean, default=False)  # rating <= 1
    reuse_count = Column(Integer, default=0)  # implicit feedback
    task_status = Column(String(20), default="")
    subtask_count = Column(Integer, default=0)
    total_duration = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "user_input": self.user_input,
            "summary": self.summary,
            "rating": self.rating,
            "tags": [t.strip() for t in self.tags.split(",") if t.strip()] if self.tags else [],
            "notes": self.notes,
            "is_recommended": self.is_recommended,
            "is_counterexample": self.is_counterexample,
            "reuse_count": self.reuse_count,
            "task_status": self.task_status,
            "subtask_count": self.subtask_count,
            "total_duration": self.total_duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
