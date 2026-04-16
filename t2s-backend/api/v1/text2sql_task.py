from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.task import TaskStatusResponse, TaskSubmitResponse
from tasks.celery_app import celery_app
from tasks.document_tasks import process_document_task, reprocess_document_task

router = APIRouter(prefix="/task", tags=["text2sql-task"])


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
    payload.error = str(result.result)
    return payload
