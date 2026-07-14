"""Worker配置数据模型"""
import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class WorkerConfig(Base):
    """Worker配置表"""
    __tablename__ = "worker_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(String(50), unique=True, nullable=False)  # leader/coder/pm/tester
    provider = Column(String(50), default="aliyun")
    model_name = Column(String(100), default="qwen-plus")
    api_base_url = Column(String(255), default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    api_key = Column(Text, default="")  # Base64编码存储
    temperature = Column(Float, default=0.3)
    max_tokens = Column(Integer, default=4096)
    timeout = Column(Integer, default=30)
    is_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
