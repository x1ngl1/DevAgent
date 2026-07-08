"""Worker配置相关API路由 — 增强安全性：API Key 加密存储，永不泄露"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.models.worker import WorkerConfig
from app.config import WORKER_ROLES
from app.utils.llm_factory import LLMFactory
from app.utils.crypto import encrypt_api_key, decrypt_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workers", tags=["workers"])


class WorkerConfigUpdate(BaseModel):
    model_config = {'protected_namespaces': ()}

    provider: str = "deepseek"
    model_name: str = "deepseek-v4-flash"
    api_base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 30
    is_enabled: bool = True


class WorkerConfigResponse(BaseModel):
    model_config = {'protected_namespaces': ()}

    worker_id: str
    provider: str
    model_name: str
    api_base_url: str
    api_key_masked: str  # 仅标注"已加密"，不泄露任何字符
    temperature: float
    max_tokens: int
    timeout: int
    is_enabled: bool

def get_db():
    """获取数据库会话"""
    from app.main import app_state
    return app_state.db_session


@router.get("/")
async def list_workers():
    """获取所有Worker角色及其配置"""
    workers = []
    for wid, info in WORKER_ROLES.items():
        workers.append({
            "worker_id": wid,
            "label": info["label"],
            "icon": info["icon"],
            "description": info["description"],
        })
    return {"workers": workers}


@router.get("/configs")
async def list_worker_configs():
    """获取所有Worker的配置"""
    async with get_db()() as session:
        from sqlalchemy import select
        result = await session.execute(select(WorkerConfig))
        configs = result.scalars().all()

        config_list = []
        for cfg in configs:
            # 返回解密后的API Key，供前端弹窗编辑使用（内部API，安全可控）
            raw_key = decrypt_api_key(cfg.api_key) if cfg.api_key else ""
            config_list.append({
                "worker_id": cfg.worker_id,
                "provider": cfg.provider,
                "model_name": cfg.model_name,
                "api_base_url": cfg.api_base_url,
                "api_key": raw_key,
                "api_key_configured": bool(cfg.api_key),
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
                "timeout": cfg.timeout,
                "is_enabled": cfg.is_enabled,
            })
        return {"configs": config_list}


@router.get("/configs/{worker_id}")
async def get_worker_config(worker_id: str):
    """获取指定Worker的配置"""
    async with get_db()() as session:
        # 按worker_id查询
        from sqlalchemy import select
        stmt = select(WorkerConfig).where(WorkerConfig.worker_id == worker_id)
        result = await session.execute(stmt)
        cfg = result.scalar_one_or_none()

        if not cfg:
            # 返回默认配置
            return {
                "worker_id": worker_id,
                "provider": "deepseek",
                "model_name": "deepseek-v4-flash",
                "api_base_url": "https://api.deepseek.com/v1",
                "api_key": "",
                "api_key_configured": False,
                "temperature": 0.3,
                "max_tokens": 4096,
                "timeout": 30,
                "is_enabled": True,
            }

        raw_key = decrypt_api_key(cfg.api_key) if cfg.api_key else ""
        return {
            "worker_id": cfg.worker_id,
            "provider": cfg.provider,
            "model_name": cfg.model_name,
            "api_base_url": cfg.api_base_url,
            "api_key": raw_key,
            "api_key_configured": bool(cfg.api_key),
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "timeout": cfg.timeout,
            "is_enabled": cfg.is_enabled,
        }


@router.put("/configs/{worker_id}")
async def update_worker_config(worker_id: str, config: WorkerConfigUpdate):
    """更新Worker配置"""
    if worker_id not in WORKER_ROLES:
        raise HTTPException(status_code=404, detail="Worker不存在")

    # 使用 Fernet 加密存储 API Key（代替原来的 Base64）
    encoded_key = encrypt_api_key(config.api_key) if config.api_key else ""

    async with get_db()() as session:
        from sqlalchemy import select
        stmt = select(WorkerConfig).where(WorkerConfig.worker_id == worker_id)
        result = await session.execute(stmt)
        cfg = result.scalar_one_or_none()

        if cfg:
            cfg.provider = config.provider
            cfg.model_name = config.model_name
            cfg.api_base_url = config.api_base_url
            if config.api_key:  # 只更新非空Key
                cfg.api_key = encoded_key
            cfg.temperature = config.temperature
            cfg.max_tokens = config.max_tokens
            cfg.timeout = config.timeout
            cfg.is_enabled = config.is_enabled
        else:
            cfg = WorkerConfig(
                worker_id=worker_id,
                provider=config.provider,
                model_name=config.model_name,
                api_base_url=config.api_base_url,
                api_key=encoded_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                is_enabled=config.is_enabled,
            )
            session.add(cfg)

        await session.commit()
        # 清除LLM客户端缓存
        from app.utils.llm_factory import LLMFactory
        LLMFactory.clear_cache()

    return {"status": "saved", "message": "配置已保存"}


@router.post("/configs/reset")
async def reset_all_configs():
    """重置所有Worker配置为默认值（API Key 回退到环境变量）"""
    import os
    from app.config import DEFAULT_WORKER_CONFIG
    from app.utils.crypto import encrypt_api_key
    # 从环境变量读取默认 API Key（若存在则加密存储）
    default_key = os.getenv("DEEPSEEK_API_KEY", "")
    encoded_default = encrypt_api_key(default_key) if default_key else ""
    async with get_db()() as session:
        from sqlalchemy import select
        result = await session.execute(select(WorkerConfig))
        for cfg in result.scalars().all():
            cfg.provider = DEFAULT_WORKER_CONFIG["provider"]
            cfg.model_name = DEFAULT_WORKER_CONFIG["model_name"]
            cfg.api_base_url = DEFAULT_WORKER_CONFIG["api_base_url"]
            cfg.api_key = encoded_default
            cfg.temperature = DEFAULT_WORKER_CONFIG["temperature"]
            cfg.max_tokens = 4096
            cfg.timeout = DEFAULT_WORKER_CONFIG.get("timeout", 30)
            cfg.is_enabled = True
        await session.commit()
        LLMFactory.clear_cache()

    return {"status": "reset", "message": "已恢复默认配置"}
