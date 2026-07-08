"""Worker配置查询服务"""
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.worker import WorkerConfig

logger = logging.getLogger(__name__)


class WorkerConfigService:
    """Worker配置查询服务"""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def get_config(self, worker_id: str) -> Optional[WorkerConfig]:
        """获取指定Worker的数据库配置"""
        async with self.session_factory() as session:
            stmt = select(WorkerConfig).where(WorkerConfig.worker_id == worker_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_configs(self) -> list:
        """获取所有Worker配置"""
        async with self.session_factory() as session:
            result = await session.execute(select(WorkerConfig))
            return result.scalars().all()

    async def is_enabled(self, worker_id: str) -> bool:
        """检查Worker是否启用"""
        config = await self.get_config(worker_id)
        return config.is_enabled if config else True
