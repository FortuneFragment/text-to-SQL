from __future__ import annotations

from core.database import SessionLocal
from core.domain_errors import (
    KnowledgeBaseConfigurationError,
    KnowledgeBaseNotFoundError,
    TaskOwnershipMismatchError,
)
from core.es_index_name import is_valid_index_name
from core.knowledge_policy import KnowledgeOperation
from repositories.es_repo import es_repo
from repositories.knowledge_file_repo import (
    KnowledgeFileRepository,
)
from services.common.knowledge_guard_service import (
    knowledge_guard,
)
from services.common.rag_service import rag_service
from tasks.celery_app import celery_app


def _run_file_task(
    *,
    file_id: int,
    task_id: str,
    reprocess: bool,
    expected_usage: str,
    expected_processor_type: str,
    process_version: int,
) -> dict:
    db = SessionLocal()
    file_repo = KnowledgeFileRepository(db)

    try:
        guard_ctx = knowledge_guard.resolve_file_for_task(
            db,
            file_id=int(file_id),
            operation=(
                KnowledgeOperation.GENERIC_REPROCESS
            ),
            task_id=task_id,
            process_version=int(process_version),
            expected_usage=expected_usage,
            expected_processor_type=(
                expected_processor_type
            ),
        )

        file_entity = guard_ctx.file
        kb_entity = guard_ctx.kb

        if file_entity is None:
            raise KnowledgeBaseNotFoundError(
                f"File ID {file_id} not found"
            )

        # Celery 重复投递同一个已完成任务时，
        # 不重复生成切片。
        if int(file_entity.status) == 2:
            return {
                "file_id": int(file_entity.id),
                "kb_id": int(file_entity.kb_id),
                "status": "already_completed",
            }

        collection_name = str(
            kb_entity.collection_name or ""
        ).strip()

        if not is_valid_index_name(
            collection_name
        ):
            raise KnowledgeBaseConfigurationError(
                "Knowledge base Elasticsearch index "
                f"name is invalid: {collection_name!r}"
            )

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

        # 先删除 ES，失败时不继续写新数据。
        es_repo.delete_chunks_by_file_id(
            int(file_entity.id),
            kb_id=int(kb_entity.id),
            index_name=collection_name,
        )

        file_repo.delete_chunks_by_file_id(
            int(file_entity.id),
            kb_id=int(kb_entity.id),
            usage_snapshot=guard_ctx.usage.value,
        )

        result = rag_service.process_and_embed_file(
            db,
            file_entity=file_entity,
            kb_entity=kb_entity,
        )

        completed = file_repo.update_status_for_task(
            int(file_entity.id),
            task_id=task_id,
            process_version=int(process_version),
            status=2,
            error_msg=None,
        )

        if not completed:
            raise TaskOwnershipMismatchError(
                "Task lost ownership while finalizing"
            )

        return {
            "file_id": int(file_entity.id),
            "kb_id": int(file_entity.kb_id),
            "mode": (
                "reprocess"
                if reprocess
                else "process"
            ),
            **result,
        }

    except Exception as exc:
        # 带 task_id 和版本更新。
        # 如果当前任务已经过期，更新会自动失败，
        # 不会覆盖新任务状态。
        file_repo.update_status_for_task(
            int(file_id),
            task_id=task_id,
            process_version=int(process_version),
            status=3,
            error_msg=str(exc)[:1000],
        )
        raise

    finally:
        db.close()


@celery_app.task(
    name="text2sql.tasks.process_document",
    bind=True,
    max_retries=0,
)
def process_document_task(
    self,
    file_id: int,
    expected_usage: str,
    expected_processor_type: str,
    process_version: int,
) -> dict:
    task_id = str(self.request.id or "").strip()

    self.update_state(state="STARTED")

    return _run_file_task(
        file_id=int(file_id),
        task_id=task_id,
        reprocess=False,
        expected_usage=expected_usage,
        expected_processor_type=(
            expected_processor_type
        ),
        process_version=int(process_version),
    )


@celery_app.task(
    name="text2sql.tasks.reprocess_document",
    bind=True,
    max_retries=0,
)
def reprocess_document_task(
    self,
    file_id: int,
    expected_usage: str,
    expected_processor_type: str,
    process_version: int,
) -> dict:
    task_id = str(self.request.id or "").strip()

    self.update_state(state="STARTED")

    return _run_file_task(
        file_id=int(file_id),
        task_id=task_id,
        reprocess=True,
        expected_usage=expected_usage,
        expected_processor_type=(
            expected_processor_type
        ),
        process_version=int(process_version),
    )
