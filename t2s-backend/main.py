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
    """中文备注：处理startup相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 变量构建：计算并更新 `connected_middlewares`。
    connected_middlewares = wait_for_docker_middlewares(engine)
    Base.metadata.create_all(bind=engine)
    # 2. 条件分支：根据当前状态选择不同处理路径。
    if connected_middlewares:
        print("[startup] 已连接中间件: " + ", ".join(connected_middlewares))


@app.get("/health")
def health() -> dict:
    """中文备注：处理相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 返回结果：输出当前函数最终结果。
    return {
        "ok": True,
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


app.include_router(text2sql_router, prefix=settings.API_V1_STR)

