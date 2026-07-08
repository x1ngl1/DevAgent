"""Task and subtask data models with checkpoint support"""
import uuid
import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

def generate_task_id():
    today = datetime.date.today().strftime("%Y%m%d")
    return f"T{today}_{uuid.uuid4().hex[:4].upper()}"

def generate_subtask_id():
    return f"S{uuid.uuid4().hex[:4].upper()}"


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String(50), primary_key=True, default=generate_task_id)
    user_input = Column(Text, nullable=False)
    status = Column(String(20), default="pending")
    zip_url = Column(String(255), nullable=True)
    error_msg = Column(Text, nullable=True)
    checkpoint_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    subtasks = relationship("Subtask", back_populates="task", cascade="all, delete-orphan")


class Subtask(Base):
    __tablename__ = "subtasks"
    id = Column(String(50), primary_key=True, default=generate_subtask_id)
    task_id = Column(String(50), ForeignKey("tasks.id"), nullable=False)
    role = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    output_summary = Column(Text, nullable=True)
    output_file = Column(String(255), nullable=True)
    duration = Column(Integer, nullable=True)
    error_msg = Column(Text, nullable=True)
    depends_on = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0)
    task = relationship("Task", back_populates="subtasks")