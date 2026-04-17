from __future__ import annotations

from core.config import settings
from core.database import SessionLocal
from core.milvus_name import normalize_collection_name
from repositories.knowledge_base_repo import KnowledgeBaseRepository
from repositories.knowledge_file_repo import KnowledgeFileRepository
from repositories.milvus_repo import milvus_repo
from services.rag_service import rag_service
from tasks.celery_app import celery_app


def _ensure_valid_collection_name(
    kb_repo: KnowledgeBaseRepository,
    kb_id: int,
    collection_name: str,
) -> str:
    """中文备注：处理_ensure_valid_collection_name相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    normalized = normalize_collection_name(collection_name)
    if normalized == str(collection_name):
        return normalized

    used_names = {item.collection_name for item in kb_repo.list_all() if int(item.id) != int(kb_id)}
    candidate = normalized
    index = 1
    while candidate in used_names:
        suffix = f"_{index}"
        limit = max(1, 128 - len(suffix))
        candidate = f"{normalized[:limit]}{suffix}"
        index += 1

    entity = kb_repo.get_by_id(int(kb_id))
    if entity is not None:
        entity.collection_name = candidate
        kb_repo.update(entity)
    return candidate


def _run_file_task(file_id: int, *, reprocess: bool) -> dict:
    """中文备注：处理_run_file_task相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    db = SessionLocal()
    file_repo = KnowledgeFileRepository(db)
    kb_repo = KnowledgeBaseRepository(db)

    try:
        file_entity = file_repo.get_by_id(int(file_id))
        if file_entity is None:
            return {"file_id": int(file_id), "status": "missing"}

        kb_entity = kb_repo.get_by_id(int(file_entity.kb_id))
        if kb_entity is None:
            file_repo.update_status(int(file_entity.id), status=3, error_msg="Knowledge base not found")
            return {"file_id": int(file_id), "status": "kb_not_found"}

        kb_entity.collection_name = _ensure_valid_collection_name(
            kb_repo,
            kb_id=int(kb_entity.id),
            collection_name=str(kb_entity.collection_name),
        )

        file_repo.update_status(int(file_entity.id), status=1, error_msg=None)

        # Retry-safe cleanup: avoid duplicated chunks/vectors after task retry.
        file_repo.delete_chunks_by_file_id(int(file_entity.id))
        try:
            milvus_repo.delete_chunks_by_file_id(
                int(file_entity.id),
                collection_name=kb_entity.collection_name,
                vector_dim=int(settings.MILVUS_VECTOR_DIM),
            )
        except Exception:
            pass

        result = rag_service.process_and_embed_file(
            db,
            file_entity=file_entity,
            kb_entity=kb_entity,
        )
        file_repo.update_status(int(file_entity.id), status=2, error_msg=None)

        return {
            "file_id": int(file_entity.id),
            "kb_id": int(file_entity.kb_id),
            "mode": "reprocess" if reprocess else "process",
            **result,
        }
    except Exception as exc:  # noqa: BLE001
        file_repo.update_status(int(file_id), status=3, error_msg=str(exc)[:1000])
        raise
    finally:
        db.close()


@celery_app.task(name="text2sql.tasks.process_document", bind=True, max_retries=3)
def process_document_task(self, file_id: int) -> dict:
    """中文备注：处理process_document_task相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    self.update_state(state="STARTED")
    try:
        return _run_file_task(file_id, reprocess=False)
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc, countdown=3)


@celery_app.task(name="text2sql.tasks.reprocess_document", bind=True, max_retries=3)
def reprocess_document_task(self, file_id: int) -> dict:
    """中文备注：处理reprocess_document_task相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    self.update_state(state="STARTED")
    try:
        return _run_file_task(file_id, reprocess=True)
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc, countdown=3)
