from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from core.database import get_db
from core.domain_errors import (
    FileProcessorMismatchError,
    FileUsageSnapshotMismatchError,
    KnowledgeBaseNotFoundError,
    KnowledgeOperationForbiddenError,
    KnowledgeUsageMismatchError,
)
from services.common.knowledge_file_service import (
    knowledge_file_service,
)
from core.config import settings
from schemas.task import TaskStatusResponse
from schemas.task import TaskSubmitResponse
from tasks.celery_app import celery_app

router = APIRouter(prefix="/task", tags=["text2sql-task"])
logger = logging.getLogger(__name__)


def _ensure_task_feature_enabled() -> None:
    if not settings.KB_ENABLED:
        raise HTTPException(status_code=400, detail="Knowledge task feature is disabled")
    if str(settings.KB_ASYNC_BACKEND).lower() != "celery":
        raise HTTPException(status_code=400, detail="Only celery async backend is currently supported")


def _format_task_error(error: object) -> str:
    return "任务执行失败，请稍后重试"


@router.post(
    "/file/{file_id}/process",
    response_model=TaskSubmitResponse,
)
def submit_file_process_task(
    file_id: int,
    db: Session = Depends(get_db),
):
    _ensure_task_feature_enabled()

    try:
        task_id = (
            knowledge_file_service.reprocess_file(
                db=db,
                file_id=int(file_id),
            )
        )

        return TaskSubmitResponse(
            task_id=task_id,
            status="queued",
            message="File process task submitted",
        )

    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
    except KnowledgeOperationForbiddenError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )
    except (
        KnowledgeUsageMismatchError,
        FileProcessorMismatchError,
        FileUsageSnapshotMismatchError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post(
    "/file/{file_id}/reprocess",
    response_model=TaskSubmitResponse,
)
def submit_file_reprocess_task(
    file_id: int,
    db: Session = Depends(get_db),
):
    _ensure_task_feature_enabled()

    try:
        task_id = (
            knowledge_file_service.reprocess_file(
                db=db,
                file_id=int(file_id),
            )
        )

        return TaskSubmitResponse(
            task_id=task_id,
            status="queued",
            message="File reprocess task submitted",
        )

    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
    except KnowledgeOperationForbiddenError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )
    except (
        KnowledgeUsageMismatchError,
        FileProcessorMismatchError,
        FileUsageSnapshotMismatchError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    result = celery_app.AsyncResult(task_id)
    payload = TaskStatusResponse(
        task_id=task_id,
        status=result.state,
        ready=result.ready(),
    )

    if not result.ready():
        return payload
    if result.successful():
        payload.successful = True
        raw = result.result
        payload.result = raw if isinstance(raw, dict) else {"value": raw}
        return payload

    payload.successful = False
    logger.error("task failed: task_id=%s state=%s error=%r", task_id, result.state, result.result)
    payload.error = _format_task_error(result.result)
    return payload
