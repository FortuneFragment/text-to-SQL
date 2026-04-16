from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: str
    message: str = ""


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    ready: bool
    successful: bool | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
