from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from api.v1.auth import router as auth_router
from api.v1.document_qa import compat_router as document_qa_compat_router
from api.v1.document_qa import router as document_qa_router
from api.v1.document_qa import admin_router as document_qa_admin_router
from api.v1.text2sql import router as text2sql_router
from api.v1.text2sql_model_config import compat_router as model_config_compat_router
from core.auth import require_info_admin
from core.config import settings
from core.database import engine
from core.startup_waiter import wait_for_docker_middlewares
from core.domain_errors import (
    KnowledgeBaseNotFoundError,
    InvalidKnowledgeUsageError,
    KnowledgeUsageMismatchError,
    KnowledgeOperationForbiddenError,
    TaskVersionStaleError,
    FileProcessorMismatchError,
    FileUsageSnapshotMismatchError,
    DataDictionaryDisabledError,
    KnowledgeUsageImmutableError,
    TaskOwnershipMismatchError,
    TaskPayloadInvalidError,
    TableArtifactNotFoundError,
    TableArtifactContextMismatchError,
)

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

# Domain exceptions mapping to HTTP responses
@app.exception_handler(KnowledgeBaseNotFoundError)
def kb_not_found_handler(request: Request, exc: KnowledgeBaseNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(KnowledgeOperationForbiddenError)
def operation_forbidden_handler(request: Request, exc: KnowledgeOperationForbiddenError):
    return JSONResponse(status_code=403, content={"detail": str(exc)})

@app.exception_handler(DataDictionaryDisabledError)
def data_dictionary_disabled_handler(request: Request, exc: DataDictionaryDisabledError):
    return JSONResponse(status_code=403, content={"detail": str(exc)})

@app.exception_handler(InvalidKnowledgeUsageError)
def invalid_usage_handler(request: Request, exc: InvalidKnowledgeUsageError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.exception_handler(KnowledgeUsageMismatchError)
def usage_mismatch_handler(request: Request, exc: KnowledgeUsageMismatchError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.exception_handler(TaskVersionStaleError)
def task_version_stale_handler(request: Request, exc: TaskVersionStaleError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.exception_handler(FileProcessorMismatchError)
def file_processor_mismatch_handler(request: Request, exc: FileProcessorMismatchError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.exception_handler(FileUsageSnapshotMismatchError)
def file_usage_snapshot_mismatch_handler(request: Request, exc: FileUsageSnapshotMismatchError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(KnowledgeUsageImmutableError)
def usage_immutable_handler(request: Request, exc: KnowledgeUsageImmutableError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(TaskOwnershipMismatchError)
def task_ownership_handler(request: Request, exc: TaskOwnershipMismatchError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(TaskPayloadInvalidError)
def task_payload_handler(request: Request, exc: TaskPayloadInvalidError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(TableArtifactNotFoundError)
def table_artifact_not_found_handler(request: Request, exc: TableArtifactNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(TableArtifactContextMismatchError)
def table_artifact_context_handler(request: Request, exc: TableArtifactContextMismatchError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

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

app.include_router(
    auth_router,
    prefix=settings.API_V1_STR,
)

app.include_router(
    text2sql_router,
    prefix=settings.API_V1_STR,
)

app.include_router(
    document_qa_router,
    prefix=settings.API_V1_STR,
)

app.include_router(
    document_qa_admin_router,
    prefix=settings.API_V1_STR,
)

# 旧兼容管理接口也必须保护
app.include_router(
    document_qa_compat_router,
    prefix=settings.API_V1_STR,
    dependencies=[Depends(require_info_admin)],
)

app.include_router(
    model_config_compat_router,
    prefix=settings.API_V1_STR,
    dependencies=[Depends(require_info_admin)],
)

if (
    settings.ENVIRONMENT == "development"
    and settings.ENABLE_DEV_LOGIN
):
    from api.v1.dev_auth import router as dev_auth_router

    app.include_router(
        dev_auth_router,
        prefix=settings.API_V1_STR,
    )
