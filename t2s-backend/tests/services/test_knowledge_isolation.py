from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.domain_errors import (
    FileProcessorMismatchError,
    FileUsageSnapshotMismatchError,
    KnowledgeUsageImmutableError,
    DataDictionaryDisabledError,
    KnowledgeOperationForbiddenError,
    TaskOwnershipMismatchError,
    TaskVersionStaleError,
)
from core.knowledge_policy import KnowledgeUsage, KnowledgeOperation, ProcessorType
from models.knowledge_base import KnowledgeBase
from models.knowledge_file import KnowledgeFile
from models.document_chunk import DocumentChunk
from models.table_semantic_artifact import TableSemanticArtifact
from services.common.knowledge_service import knowledge_service
from services.common.knowledge_guard_service import knowledge_guard
from services.common.rag_service import rag_service
from repositories.es_repo import ElasticsearchRepository
from repositories.knowledge_base_repo import KnowledgeBaseRepository
from repositories.knowledge_file_repo import KnowledgeFileRepository
from schemas.knowledge import KnowledgeBaseCreateRequest, KnowledgeBaseUpdateRequest


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    # Create all tables in metadata
    KnowledgeBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_kb_immutable_usage(session):
    kb = knowledge_service.create_kb(
        session,
        KnowledgeBaseCreateRequest(
            name="test_kb",
            usage=KnowledgeUsage.TABLE_ROUTE.value,
        )
    )
    assert kb.usage == KnowledgeUsage.TABLE_ROUTE.value

    # Update name should succeed
    updated = knowledge_service.update_kb(
        session,
        kb.id,
        KnowledgeBaseUpdateRequest(name="new_kb_name")
    )
    assert updated.name == "new_kb_name"

    # Update usage via request payload should raise ValidationError
    with pytest.raises(ValidationError):
        KnowledgeBaseUpdateRequest(usage=KnowledgeUsage.FEW_SHOT.value)

    updated.usage = KnowledgeUsage.FEW_SHOT.value
    with pytest.raises(KnowledgeUsageImmutableError):
        KnowledgeBaseRepository(session).update(updated)
    session.rollback()


def test_kb_data_dictionary_disabled(session, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DICTIONARY_FEATURE_ENABLED", False)

    # Creating data dictionary KB when feature is disabled should fail
    with pytest.raises(DataDictionaryDisabledError):
        knowledge_service.create_kb(
            session,
            KnowledgeBaseCreateRequest(
                name="dict_kb",
                usage=KnowledgeUsage.DATA_DICTIONARY.value,
            )
        )


def test_delete_kb_physically_removes_row(session, monkeypatch):
    kb = knowledge_service.create_kb(
        session,
        KnowledgeBaseCreateRequest(
            name="physical_delete_kb",
            usage=KnowledgeUsage.DOCUMENT_QA.value,
        ),
    )
    kb_id = int(kb.id)
    knowledge_module = importlib.import_module(
        "services.common.knowledge_service"
    )
    monkeypatch.setattr(
        knowledge_module.es_repo,
        "delete_index",
        lambda _index_name: None,
    )

    knowledge_service.delete_kb(session, kb_id)

    assert session.get(KnowledgeBase, kb_id) is None


def test_document_parsing_tasks_disable_automatic_retry():
    from tasks.document_tasks import (
        process_document_task,
        reprocess_document_task,
    )
    from tasks.table_semantic_tasks import (
        process_table_semantic_task,
    )

    assert process_document_task.max_retries == 0
    assert reprocess_document_task.max_retries == 0
    assert process_table_semantic_task.max_retries == 0


def test_guard_service_resolutions(session):
    kb_route = knowledge_service.create_kb(
        session,
        KnowledgeBaseCreateRequest(
            name="route_kb",
            usage=KnowledgeUsage.TABLE_ROUTE.value,
        )
    )
    kb_shot = knowledge_service.create_kb(
        session,
        KnowledgeBaseCreateRequest(
            name="few_shot_kb",
            usage=KnowledgeUsage.FEW_SHOT.value,
        )
    )

    # Route search on route KB allowed
    ctx = knowledge_guard.resolve_kb_for_operation(session, kb_route.id, KnowledgeOperation.TABLE_ROUTE_SEARCH)
    assert ctx.usage == KnowledgeUsage.TABLE_ROUTE

    # Route search on few_shot KB not allowed
    with pytest.raises(KnowledgeOperationForbiddenError):
        knowledge_guard.resolve_kb_for_operation(session, kb_shot.id, KnowledgeOperation.TABLE_ROUTE_SEARCH)


def test_guard_service_file_resolutions(session):
    kb = knowledge_service.create_kb(
        session,
        KnowledgeBaseCreateRequest(
            name="route_kb",
            usage=KnowledgeUsage.TABLE_ROUTE.value,
        )
    )
    file_entity = KnowledgeFile(
        id=1,
        kb_id=kb.id,
        file_name="test.txt",
        file_type="txt",
        file_size=100,
        md5="some_md5",
        status=1,
        minio_bucket="test-bucket",
        minio_object_name="test-object",
        is_deleted=False,
        usage_snapshot=KnowledgeUsage.TABLE_ROUTE.value,
        processor_type=ProcessorType.GENERIC_DOCUMENT.value,
        process_version=1,
    )
    session.add(file_entity)
    session.commit()

    # Resolve file for allowed delete operation
    ctx = knowledge_guard.resolve_file_for_operation(session, file_entity.id, KnowledgeOperation.GENERIC_FILE_DELETE)
    assert ctx.usage == KnowledgeUsage.TABLE_ROUTE
    assert ctx.processor_type == ProcessorType.GENERIC_DOCUMENT


def _create_route_file(
    session,
    *,
    usage_snapshot: str = KnowledgeUsage.TABLE_ROUTE.value,
    processor_type: str = ProcessorType.GENERIC_DOCUMENT.value,
) -> KnowledgeFile:
    kb = knowledge_service.create_kb(
        session,
        KnowledgeBaseCreateRequest(
            name=f"route_kb_{usage_snapshot}_{processor_type}",
            usage=KnowledgeUsage.TABLE_ROUTE.value,
        ),
    )
    file_entity = KnowledgeFile(
        id=int(kb.id) * 100,
        kb_id=kb.id,
        file_name="test.txt",
        file_type="txt",
        file_size=4,
        md5=f"md5_{kb.id}",
        status=0,
        task_id="task-current",
        minio_bucket="test-bucket",
        minio_object_name="test-object",
        is_deleted=False,
        usage_snapshot=usage_snapshot,
        processor_type=processor_type,
        process_version=2,
    )
    session.add(file_entity)
    session.commit()
    session.refresh(file_entity)
    return file_entity


def test_guard_rejects_file_usage_snapshot_mismatch(session, monkeypatch):
    kb = knowledge_service.create_kb(
        session,
        KnowledgeBaseCreateRequest(
            name="route_kb_mismatch_1",
            usage=KnowledgeUsage.TABLE_ROUTE.value,
        ),
    )
    file_entity = KnowledgeFile(
        id=998,
        kb_id=kb.id,
        file_name="test.txt",
        file_type="txt",
        file_size=4,
        md5="md5_998",
        status=0,
        task_id="task-current",
        minio_bucket="test-bucket",
        minio_object_name="test-object",
        is_deleted=False,
        usage_snapshot=KnowledgeUsage.DOCUMENT_QA.value,
        processor_type=ProcessorType.GENERIC_DOCUMENT.value,
        process_version=2,
    )
    monkeypatch.setattr(
        KnowledgeFileRepository,
        "get_with_kb",
        lambda self, file_id: (file_entity, kb) if file_id == 998 else None,
    )
    with pytest.raises(FileUsageSnapshotMismatchError):
        knowledge_guard.resolve_file_for_operation(
            session,
            998,
            KnowledgeOperation.GENERIC_FILE_READ,
        )


def test_guard_rejects_file_processor_mismatch(session, monkeypatch):
    kb = knowledge_service.create_kb(
        session,
        KnowledgeBaseCreateRequest(
            name="route_kb_mismatch_2",
            usage=KnowledgeUsage.TABLE_ROUTE.value,
        ),
    )
    file_entity = KnowledgeFile(
        id=999,
        kb_id=kb.id,
        file_name="test.txt",
        file_type="txt",
        file_size=4,
        md5="md5_999",
        status=0,
        task_id="task-current",
        minio_bucket="test-bucket",
        minio_object_name="test-object",
        is_deleted=False,
        usage_snapshot=KnowledgeUsage.TABLE_ROUTE.value,
        processor_type=ProcessorType.FEW_SHOT.value,
        process_version=2,
    )
    monkeypatch.setattr(
        KnowledgeFileRepository,
        "get_with_kb",
        lambda self, file_id: (file_entity, kb) if file_id == 999 else None,
    )
    with pytest.raises(FileProcessorMismatchError):
        knowledge_guard.resolve_file_for_operation(
            session,
            999,
            KnowledgeOperation.GENERIC_FILE_READ,
        )


def test_task_guard_rejects_stale_version_and_owner(session):
    file_entity = _create_route_file(session)

    with pytest.raises(TaskVersionStaleError):
        knowledge_guard.resolve_file_for_task(
            session,
            file_id=file_entity.id,
            operation=KnowledgeOperation.GENERIC_REPROCESS,
            task_id="task-current",
            process_version=1,
            expected_usage=KnowledgeUsage.TABLE_ROUTE.value,
            expected_processor_type=(
                ProcessorType.GENERIC_DOCUMENT.value
            ),
        )

    with pytest.raises(TaskOwnershipMismatchError):
        knowledge_guard.resolve_file_for_task(
            session,
            file_id=file_entity.id,
            operation=KnowledgeOperation.GENERIC_REPROCESS,
            task_id="task-old",
            process_version=2,
            expected_usage=KnowledgeUsage.TABLE_ROUTE.value,
            expected_processor_type=(
                ProcessorType.GENERIC_DOCUMENT.value
            ),
        )


def test_rag_writes_isolation_context(
    session,
    monkeypatch,
):
    file_entity = _create_route_file(session)
    kb = session.get(KnowledgeBase, file_entity.kb_id)
    indexed_rows: list[dict] = []
    saved_chunks: list[DocumentChunk] = []
    rag_module = importlib.import_module(
        "services.common.rag_service"
    )

    class FakeEmbeddings:
        @staticmethod
        def embed_documents(texts):
            return [[0.1, 0.2] for _ in texts]

    class FakeChunkRepository:
        def __init__(self, _db):
            pass

        @staticmethod
        def bulk_create_chunks(chunks):
            for index, chunk in enumerate(chunks, start=1):
                chunk.id = index
            saved_chunks.extend(chunks)
            return chunks

    monkeypatch.setattr(
        rag_module.minio_repo,
        "get_file_bytes",
        lambda _object_name: b"test content",
    )
    monkeypatch.setattr(
        rag_module,
        "get_embeddings",
        lambda _db: FakeEmbeddings(),
    )
    monkeypatch.setattr(
        rag_module,
        "get_embedding_vector_dim",
        lambda _db: 2,
    )
    monkeypatch.setattr(
        rag_module.es_repo,
        "insert_chunks",
        lambda rows, **_kwargs: indexed_rows.extend(rows),
    )
    monkeypatch.setattr(
        rag_module,
        "KnowledgeFileRepository",
        FakeChunkRepository,
    )

    rag_service.process_and_embed_file(
        session,
        file_entity=file_entity,
        kb_entity=kb,
    )

    assert saved_chunks
    assert {
        chunk.usage_snapshot for chunk in saved_chunks
    } == {KnowledgeUsage.TABLE_ROUTE.value}
    assert {
        chunk.processor_type for chunk in saved_chunks
    } == {ProcessorType.GENERIC_DOCUMENT.value}
    assert indexed_rows
    assert {
        row["usage_type"] for row in indexed_rows
    } == {KnowledgeUsage.TABLE_ROUTE.value}
    assert {
        row["processor_type"] for row in indexed_rows
    } == {ProcessorType.GENERIC_DOCUMENT.value}


def test_es_search_requires_usage_in_strict_mode(
    monkeypatch,
):
    class FakeIndices:
        @staticmethod
        def exists(*, index):
            return bool(index)

    class FakeClient:
        indices = FakeIndices()

    repo = object.__new__(ElasticsearchRepository)
    repo.client = FakeClient()
    monkeypatch.setattr(
        settings,
        "KB_USAGE_STRICT_ES_FILTER",
        True,
    )

    with pytest.raises(ValueError, match="expected_usage"):
        repo.search_chunks(
            index_name="test-index",
            vector_dim=2,
            kb_id=1,
            query_vector=[0.1, 0.2],
            top_k=3,
        )
