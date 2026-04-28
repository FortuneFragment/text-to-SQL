from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.task import TaskStatusResponse, TaskSubmitResponse
from tasks.celery_app import celery_app
from tasks.document_tasks import process_document_task, reprocess_document_task

router = APIRouter(prefix="/task", tags=["text2sql-task"])
logger = logging.getLogger(__name__)


def _ensure_task_feature_enabled() -> None:
    if not settings.KB_ENABLED:
        raise HTTPException(status_code=400, detail="Knowledge task feature is disabled")
    if str(settings.KB_ASYNC_BACKEND).lower() != "celery":
        raise HTTPException(status_code=400, detail="Only celery async backend is currently supported")


@router.post("/file/{file_id}/process", response_model=TaskSubmitResponse)
def submit_file_process_task(file_id: int):
    _ensure_task_feature_enabled()
    task = process_document_task.delay(int(file_id))
    return TaskSubmitResponse(task_id=task.id, status="queued", message="File process task submitted")


@router.post("/file/{file_id}/reprocess", response_model=TaskSubmitResponse)
def submit_file_reprocess_task(file_id: int):
    _ensure_task_feature_enabled()
    task = reprocess_document_task.delay(int(file_id))
    return TaskSubmitResponse(task_id=task.id, status="queued", message="File reprocess task submitted")


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
    payload.error = "\u4efb\u52a1\u6267\u884c\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5"
    return payload
