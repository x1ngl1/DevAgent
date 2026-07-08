from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.api import task, worker, sse, chat
from app.models.database import init_db, async_session_factory
from app.services.worker_config_service import WorkerConfigService
from app.services.task_service import TaskService
from app.api.sse import sse_manager
from app.services.conversation_service import ConversationService

class AppState:
    def __init__(self):
        self.db_session = None

app_state = AppState()

app = FastAPI(title="AI开发团队", version="1.0.0")

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

@app.on_event("startup")
async def startup():
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting up - initializing database...")
    try:
        await init_db()
        app_state.db_session = async_session_factory
        app_state.worker_config_service = WorkerConfigService(async_session_factory)
        app_state.task_service = TaskService(async_session_factory, app_state.worker_config_service)

        # Wire SSE callback - connect TaskService to SSE manager
        async def sse_bridge(event_type: str, data: dict):
            await sse_manager.broadcast(event_type, data)
        app_state.task_service.set_sse_callback(sse_bridge)

        # Wire ConversationService SSE callback
        conv_service = ConversationService(app_state.worker_config_service, sse_bridge)
        app_state.task_service.conversation_service = conv_service

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
