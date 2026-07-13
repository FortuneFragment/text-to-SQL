from __future__ import annotations

from core.database import SessionLocal
from core.domain_errors import (
    KnowledgeBaseNotFoundError,
    TaskOwnershipMismatchError,
    TaskPayloadInvalidError,
)
from core.knowledge_policy import KnowledgeOperation
from repositories.knowledge_file_repo import (
    KnowledgeFileRepository,
)
from services.common.knowledge_guard_service import (
    knowledge_guard,
)
from services.document_qa import (
    table_semantic_service,
)
from tasks.celery_app import celery_app


@celery_app.task(
    name="document_qa.tasks.process_table_semantic",
    bind=True,
    max_retries=0,
)
def process_table_semantic_task(
    self,
    file_id: int,
    batch_id: str,
    sheet_jobs: list[dict],
    expected_usage: str,
    expected_processor_type: str,
    process_version: int,
) -> dict:
    task_id = str(self.request.id or "").strip()

    db = SessionLocal()
    file_repo = KnowledgeFileRepository(db)

    try:
        if not isinstance(sheet_jobs, list):
            raise TaskPayloadInvalidError(
                "sheet_jobs must be a list"
            )

        if not sheet_jobs:
            raise TaskPayloadInvalidError(
                "sheet_jobs cannot be empty"
            )

        total_sheets = len(sheet_jobs)

        table_ids = [
            str(item.get("table_id") or "")
            for item in sheet_jobs
        ]

        sheet_names = [
            str(item.get("sheet_name") or "")
            for item in sheet_jobs
        ]

        last_progress: dict = {
            "file_id": int(file_id),
            "batch_id": str(batch_id),
            "state": "PENDING",

            "total_sheets": total_sheets,
            "completed_sheets": 0,
            "progress": 0.0,

            "table_ids": table_ids,
            "sheet_names": sheet_names,

            "completed_table_ids": [],
            "current_table_id": None,
            "current_sheet_name": None,

            "error": None,
        }

        self.update_state(
            state="PROGRESS",
            meta=last_progress,
        )

        guard_ctx = (
            knowledge_guard.resolve_file_for_task(
                db,
                file_id=int(file_id),
                operation=(
                    KnowledgeOperation.TABLE_UPLOAD
                ),
                task_id=task_id,
                process_version=int(
                    process_version
                ),
                expected_usage=expected_usage,
                expected_processor_type=(
                    expected_processor_type
                ),
            )
        )

        file_entity = guard_ctx.file

        if file_entity is None:
            raise KnowledgeBaseNotFoundError(
                f"File ID {file_id} not found"
            )

        if int(file_entity.status) == 2:
            return {
                "file_id": int(file_entity.id),
                "kb_id": int(file_entity.kb_id),
                "status": "already_completed",
            }

        started = file_repo.update_status_for_task(
            int(file_entity.id),
            task_id=task_id,
            process_version=int(process_version),
            status=1,
            error_msg=None,
        )

        if not started:
            raise TaskOwnershipMismatchError(
                "Task lost ownership before processing"
            )

        last_progress["state"] = "STARTED"

        persisted = (
            file_repo
            .update_table_task_meta_for_task(
                int(file_entity.id),
                task_id=task_id,
                process_version=int(
                    process_version
                ),
                task_meta=last_progress,
            )
        )

        if not persisted:
            raise TaskOwnershipMismatchError(
                "Task lost ownership while "
                "persisting initial progress"
            )

        def report_progress(
            progress_meta: dict,
        ) -> None:
            nonlocal last_progress

            last_progress = {
                **last_progress,
                **progress_meta,
                "file_id": int(file_id),
                "batch_id": str(batch_id),
                "state": "PROGRESS",
                "error": None,
            }

            persisted = (
                file_repo
                .update_table_task_meta_for_task(
                    int(file_id),
                    task_id=task_id,
                    process_version=int(
                        process_version
                    ),
                    task_meta=last_progress,
                )
            )

            if not persisted:
                raise TaskOwnershipMismatchError(
                    "Task lost ownership while "
                    "persisting progress"
                )

            self.update_state(
                state="PROGRESS",
                meta=last_progress,
            )

        result = (
            table_semantic_service
            .process_table_batch(
                db,
                file_entity=file_entity,
                batch_id=str(batch_id),
                sheet_jobs=sheet_jobs,
                progress_callback=report_progress,
            )
        )

        success_meta = {
            **last_progress,
            **result,
            "file_id": int(file_id),
            "batch_id": str(batch_id),
            "state": "SUCCESS",

            "completed_sheets": total_sheets,
            "progress": 1.0,

            "current_table_id": None,
            "current_sheet_name": None,

            "error": None,
        }

        persisted = (
            file_repo
            .update_table_task_meta_for_task(
                int(file_id),
                task_id=task_id,
                process_version=int(
                    process_version
                ),
                task_meta=success_meta,
            )
        )

        if not persisted:
            raise TaskOwnershipMismatchError(
                "Task lost ownership while "
                "persisting final result"
            )

        completed = (
            file_repo.update_status_for_task(
                int(file_entity.id),
                task_id=task_id,
                process_version=int(
                    process_version
                ),
                status=2,
                error_msg=None,
            )
        )

        if not completed:
            raise TaskOwnershipMismatchError(
                "Task lost ownership while finalizing"
            )

        return result

    except Exception as exc:
        db.rollback()

        failure_meta = {
            **last_progress,
            "file_id": int(file_id),
            "batch_id": str(batch_id),
            "state": "FAILURE",
            "error": (
                f"{exc.__class__.__name__}: "
                f"{exc}"
            )[:1000],
            "current_table_id": None,
            "current_sheet_name": None,
        }

        try:
            file_repo.update_table_task_meta_for_task(
                int(file_id),
                task_id=task_id,
                process_version=int(
                    process_version
                ),
                task_meta=failure_meta,
            )
        except Exception:
            db.rollback()

        file_repo.update_status_for_task(
            int(file_id),
            task_id=task_id,
            process_version=int(
                process_version
            ),
            status=3,
            error_msg=str(exc)[:1000],
        )

        raise

    finally:
        db.close()
