from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.text2sql import router as text2sql_router
from core.config import settings
from core.database import engine
from core.startup_waiter import wait_for_docker_middlewares
from models import Base

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
    """在服务启动时检查依赖并初始化数据库表。"""
    connected_middlewares = wait_for_docker_middlewares(engine)
    Base.metadata.create_all(bind=engine)
    if connected_middlewares:
        print("[startup] 已连接中间件: " + ", ".join(connected_middlewares))

@app.get("/health")
def health() -> dict:
    """返回服务健康状态。"""
    return {
        "ok": True,
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }

app.include_router(text2sql_router, prefix=settings.API_V1_STR)

