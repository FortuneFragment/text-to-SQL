from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from api.v1.text2sql import router as text2sql_router
from api.v1.text2sql_model_config import compat_router as model_config_compat_router
from core.config import settings
from core.database import engine
from core.startup_waiter import wait_for_docker_middlewares

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    """在服务启动时检查依赖连通性。"""
    connected_middlewares = wait_for_docker_middlewares(engine)
    if connected_middlewares:
        logger = logging.getLogger(__name__)
        logger.info("已连接中间件: %s", connected_middlewares)

@app.get("/health")
def health() -> dict:
    """返回服务健康状态。"""
    return {
        "ok": True,
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }

app.include_router(text2sql_router, prefix=settings.API_V1_STR)
app.include_router(model_config_compat_router, prefix=settings.API_V1_STR)

