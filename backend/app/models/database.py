"""数据库配置和会话管理"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.task import Base as TaskBase
from app.models.worker import Base as WorkerBase
from app.models.experience import Base as ExperienceBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """初始化数据库，创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(TaskBase.metadata.create_all)
        await conn.run_sync(WorkerBase.metadata.create_all)
        await conn.run_sync(ExperienceBase.metadata.create_all)


async def get_session():
    """获取数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def get_db_session_factory():
    """返回会话工厂（用于依赖注入）"""
    return async_session_factory


def get_db_service():
    """返回数据库服务（兼容旧接口）"""
    return async_session_factory
