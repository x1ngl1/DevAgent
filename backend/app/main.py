from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.api import task, worker, sse, chat, rag, experience
from app.models.database import init_db, async_session_factory
from app.services.worker_config_service import WorkerConfigService
from app.services.task_service import TaskService
from app.api.sse import sse_manager
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService
from app.services.experience_service import ExperienceService
from app.config import WORKER_ROLES, DEFAULT_WORKER_CONFIG
from app.models.worker import WorkerConfig
from app.utils.crypto import encrypt_api_key

class AppState:
    def __init__(self):
        self.db_session = None
        self.rag_service = None
        self.experience_service = None

app_state = AppState()

app = FastAPI(title="多智能体遗留代码测试生成系统", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(task.router)
app.include_router(worker.router)
app.include_router(sse.router)
app.include_router(chat.router)
app.include_router(rag.router)
app.include_router(experience.router)

@app.get("/api/configs")
async def get_configs_compat():
    from app.api.worker import list_worker_configs
    return await list_worker_configs()

@app.put("/api/configs/{worker_id}")
async def update_config_compat(worker_id: str, config: dict):
    from app.api.worker import update_worker_config
    from app.api.worker import WorkerConfigUpdate
    config_obj = WorkerConfigUpdate(**config)
    return await update_worker_config(worker_id, config_obj)

@app.post("/api/configs/reset")
async def reset_configs_compat():
    from app.api.worker import reset_all_configs
    return await reset_all_configs()

async def init_default_worker_configs():
    """初始化所有 Worker 的默认配置（如果不存在）"""
    import os
    from sqlalchemy import select

    default_api_key = os.getenv("DEEPSEEK_API_KEY", "")
    encoded_key = encrypt_api_key(default_api_key) if default_api_key else ""

    async with async_session_factory() as session:
        for worker_id in WORKER_ROLES.keys():
            stmt = select(WorkerConfig).where(WorkerConfig.worker_id == worker_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                # 创建默认配置
                cfg = WorkerConfig(
                    worker_id=worker_id,
                    provider=DEFAULT_WORKER_CONFIG["provider"],
                    model_name=DEFAULT_WORKER_CONFIG["model_name"],
                    api_base_url=DEFAULT_WORKER_CONFIG["api_base_url"],
                    api_key=encoded_key,
                    temperature=DEFAULT_WORKER_CONFIG["temperature"],
                    max_tokens=DEFAULT_WORKER_CONFIG["max_tokens"],
                    timeout=DEFAULT_WORKER_CONFIG.get("timeout", 30),
                    is_enabled=True,
                )
                session.add(cfg)
                print(f"Created default config for {worker_id}")

        await session.commit()


@app.on_event("startup")
async def startup():
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting up - initializing database...")
    try:
        await init_db()
        app_state.db_session = async_session_factory
        app_state.worker_config_service = WorkerConfigService(async_session_factory)

        # Initialize default worker configs for all roles
        await init_default_worker_configs()

        # Init RAG service first (needed by TaskService)
        try:
            from app.services.rag_service import RAGService
            import os
            rag_config = {
                "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
                "api_base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.siliconflow.cn/v1"),
                "model_name": os.getenv("DEEPSEEK_MODEL", "Qwen/Qwen2.5-72B-Instruct-128K"),
                "temperature": 0.3,
                "max_tokens": 2048,
            }
            app_state.rag_service = RAGService(llm_config=rag_config)
            logger.info("RAG service initialized")
        except Exception as e:
            logger.warning(f"RAG service init failed (will retry on first use): {e}")

        app_state.task_service = TaskService(
            async_session_factory,
            app_state.worker_config_service,
            rag_service=app_state.rag_service,
        )

        # Wire SSE callback - connect TaskService to SSE manager
        async def sse_bridge(event_type: str, data: dict):
            await sse_manager.broadcast(event_type, data)
        app_state.task_service.set_sse_callback(sse_bridge)

        # Wire ConversationService SSE callback
        conv_service = ConversationService(app_state.worker_config_service, sse_bridge)
        app_state.task_service.conversation_service = conv_service

        # Init Experience service
        app_state.experience_service = ExperienceService(lambda: async_session_factory())
        logger.info("Experience service initialized")

        logger.info("Startup complete - SSE and services initialized")
    except Exception as e:
        logger.error(f"Startup failed: {e}")

@app.get("/health")
async def health():
    return {"status": "ok"}

DIST_DIR = "/root/Agent/frontend/dist"
if os.path.exists(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")
    app.mount("/img", StaticFiles(directory=os.path.join(DIST_DIR, "img")), name="img")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(DIST_DIR, "index.html"))

    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        path = request.url.path
        if path.startswith("/api") or path.startswith("/sse") or path.startswith("/health"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return FileResponse(os.path.join(DIST_DIR, "index.html"))
