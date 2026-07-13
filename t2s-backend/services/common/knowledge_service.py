from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from core.config import settings
from core.es_index_name import normalize_index_name
from core.knowledge_policy import (
    KnowledgeUsage,
    parse_usage,
)
from core.domain_errors import (
    DataDictionaryDisabledError,
)
from models.knowledge_base import KnowledgeBase
from models.knowledge_file import KnowledgeFile
from models.document_chunk import DocumentChunk
from models.table_semantic_artifact import TableSemanticArtifact
from repositories.knowledge_base_repo import KnowledgeBaseRepository
from repositories.knowledge_file_repo import KnowledgeFileRepository
from repositories.es_repo import es_repo
from schemas.knowledge import KnowledgeBaseCreateRequest, KnowledgeBaseUpdateRequest


class KnowledgeService:
    @staticmethod
    def _dedupe_collection_name(base_name: str, used_names: set[str]) -> str:
        candidate = str(base_name)
        if candidate not in used_names:
            return candidate

        index = 1
        while True:
            suffix = f"_{index}"
            limit = max(1, 128 - len(suffix))
            test_name = f"{candidate[:limit]}{suffix}"
            if test_name not in used_names:
                return test_name
            index += 1

    def _repair_legacy_collection_names(self, repo: KnowledgeBaseRepository) -> None:
        rows = repo.list_all()
        if not rows:
            return

        reserved = {str(item.collection_name) for item in rows}
        for entity in rows:
            original = str(entity.collection_name)
            normalized = normalize_index_name(original)
            if normalized == original:
                continue

            reserved.discard(original)
            unique_name = self._dedupe_collection_name(normalized, reserved)
            reserved.add(unique_name)

            entity.collection_name = unique_name
            repo.update(entity)

    def list_kbs(self, db: Session) -> list[KnowledgeBase]:
        repo = KnowledgeBaseRepository(db)
        self._repair_legacy_collection_names(repo)
        return repo.list_all()

    def create_kb(self, db: Session, payload: KnowledgeBaseCreateRequest) -> KnowledgeBase:
        repo = KnowledgeBaseRepository(db)
        self._repair_legacy_collection_names(repo)

        usage = parse_usage(payload.usage)
        if usage == KnowledgeUsage.DATA_DICTIONARY:
            if not getattr(settings, "DATA_DICTIONARY_FEATURE_ENABLED", False):
                raise DataDictionaryDisabledError("数据字典功能未启用")

        collection_name = normalize_index_name(
            payload.collection_name or f"{payload.name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        )
        used_names = {item.collection_name for item in repo.list_all()}
        collection_name = self._dedupe_collection_name(collection_name, used_names)

        entity = KnowledgeBase(
            name=str(payload.name).strip(),
            description=str(payload.description or "").strip(),
            collection_name=collection_name,
            usage=usage.value,
            default_chunk_size=int(payload.default_chunk_size),
            default_chunk_overlap=int(payload.default_chunk_overlap),
            embedding_model=(str(payload.embedding_model).strip() if payload.embedding_model else None),
        )
        created = repo.create(entity)
        return created

    def update_kb(
            self,
            db: Session,
            kb_id: int,
            payload: KnowledgeBaseUpdateRequest,
    ) -> KnowledgeBase:
        repo = KnowledgeBaseRepository(db)
        self._repair_legacy_collection_names(repo)

        entity = repo.get_by_id(kb_id)
        if entity is None:
            raise ValueError("Knowledge base not found")

        if payload.name is not None:
            entity.name = str(payload.name).strip()

        if payload.description is not None:
            entity.description = str(payload.description).strip()

        if payload.default_chunk_size is not None:
            entity.default_chunk_size = int(
                payload.default_chunk_size
            )

        if payload.default_chunk_overlap is not None:
            entity.default_chunk_overlap = int(
                payload.default_chunk_overlap
            )

        if (
                entity.default_chunk_overlap
                >= entity.default_chunk_size
        ):
            raise ValueError(
                "default_chunk_overlap must be smaller "
                "than default_chunk_size"
            )

        if payload.embedding_model is not None:
            entity.embedding_model = (
                    str(payload.embedding_model).strip() or None
            )

        updated = repo.update(entity)

        return updated

    def delete_kb(self, db: Session, kb_id: int) -> None:
        repo = KnowledgeBaseRepository(db)
        entity = repo.get_by_id(kb_id)
        if entity is None:
            raise ValueError("Knowledge base not found")

        # Check files count
        file_repo = KnowledgeFileRepository(db)
        _, total_files = file_repo.list_by_kb_paginated(kb_id=kb_id, page=1, page_size=1)
        if total_files > 0:
            raise ValueError("请先删除该知识库下的文件")

        # Check chunks count
        total_chunks = db.query(DocumentChunk.id).filter(DocumentChunk.kb_id == kb_id).count()
        if total_chunks > 0:
            raise ValueError("该知识库下仍有未清理的分片数据")

        # Check table semantic artifacts count
        total_artifacts = db.query(TableSemanticArtifact.id).filter(
            TableSemanticArtifact.kb_id == kb_id,
            TableSemanticArtifact.deleted_at.is_(None)
        ).count()
        if total_artifacts > 0:
            raise ValueError("请先删除该知识库下的表格解析产物")

        # Check running tasks count
        active_tasks = db.query(KnowledgeFile.id).filter(
            KnowledgeFile.kb_id == kb_id,
            KnowledgeFile.status == 1,
            KnowledgeFile.is_deleted == False
        ).count()
        if active_tasks > 0:
            raise ValueError("该知识库下有正在运行的解析任务，请稍后再试")

        try:
            es_repo.delete_index(entity.collection_name)
        except Exception as exc:
            raise ValueError(f"删除 Elasticsearch 索引失败: {exc}") from exc

        repo.delete(entity)


knowledge_service = KnowledgeService()
