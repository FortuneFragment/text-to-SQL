from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from core.config import settings
from core.milvus_name import normalize_collection_name
from models.knowledge_base import KnowledgeBase
from repositories.knowledge_base_repo import KnowledgeBaseRepository
from repositories.knowledge_file_repo import KnowledgeFileRepository
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
            normalized = normalize_collection_name(original)
            if normalized == original:
                continue

            reserved.discard(original)
            unique_name = self._dedupe_collection_name(normalized, reserved)
            reserved.add(unique_name)

            entity.collection_name = unique_name
            repo.update(entity)

    def _build_default_kb(self) -> KnowledgeBase:
        return KnowledgeBase(
            name="默认知识库",
            description="系统默认知识库",
            collection_name=normalize_collection_name(settings.MILVUS_COLLECTION),
            default_chunk_size=int(settings.KB_CHUNK_SIZE),
            default_chunk_overlap=int(settings.KB_CHUNK_OVERLAP),
            embedding_model=str(settings.EMBEDDING_MODEL or "").strip() or None,
            is_default=True,
            is_deleted=False,
        )

    def ensure_default_kb(self, db: Session) -> KnowledgeBase:
        repo = KnowledgeBaseRepository(db)
        current_default = repo.get_default()
        if current_default is not None:
            return current_default

        rows = repo.list_all()
        if rows:
            first = rows[0]
            first.is_default = True
            return repo.update(first)

        return repo.create(self._build_default_kb())

    def list_kbs(self, db: Session) -> list[KnowledgeBase]:
        self.ensure_default_kb(db)
        repo = KnowledgeBaseRepository(db)
        self._repair_legacy_collection_names(repo)
        return repo.list_all()

    def create_kb(self, db: Session, payload: KnowledgeBaseCreateRequest) -> KnowledgeBase:
        repo = KnowledgeBaseRepository(db)
        self._repair_legacy_collection_names(repo)

        collection_name = normalize_collection_name(
            payload.collection_name or f"{payload.name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        )
        used_names = {item.collection_name for item in repo.list_all()}
        collection_name = self._dedupe_collection_name(collection_name, used_names)

        entity = KnowledgeBase(
            name=str(payload.name).strip(),
            description=str(payload.description or "").strip(),
            collection_name=collection_name,
            default_chunk_size=int(payload.default_chunk_size),
            default_chunk_overlap=int(payload.default_chunk_overlap),
            embedding_model=(str(payload.embedding_model).strip() if payload.embedding_model else None),
            is_default=False,
            is_deleted=False,
        )
        created = repo.create(entity)
        if len(repo.list_all()) == 1:
            created.is_default = True
            created = repo.update(created)
        return created

    def update_kb(self, db: Session, kb_id: int, payload: KnowledgeBaseUpdateRequest) -> KnowledgeBase:
        repo = KnowledgeBaseRepository(db)
        self._repair_legacy_collection_names(repo)

        entity = repo.get_by_id(kb_id)
        if entity is None:
            raise ValueError("Knowledge base not found")

        if payload.name is not None:
            entity.name = str(payload.name).strip()
        if payload.description is not None:
            entity.description = str(payload.description).strip()
        if payload.collection_name is not None:
            normalized = normalize_collection_name(payload.collection_name)
            used_names = {item.collection_name for item in repo.list_all() if int(item.id) != int(entity.id)}
            entity.collection_name = self._dedupe_collection_name(normalized, used_names)

        if payload.default_chunk_size is not None:
            entity.default_chunk_size = int(payload.default_chunk_size)
        if payload.default_chunk_overlap is not None:
            entity.default_chunk_overlap = int(payload.default_chunk_overlap)

        if entity.default_chunk_overlap >= entity.default_chunk_size:
            raise ValueError("default_chunk_overlap must be smaller than default_chunk_size")

        if payload.embedding_model is not None:
            entity.embedding_model = str(payload.embedding_model).strip() or None

        if payload.is_default is True and not entity.is_default:
            repo.clear_default_flag()
            entity.is_default = True

        updated = repo.update(entity)
        self.ensure_default_kb(db)
        return updated

    def delete_kb(self, db: Session, kb_id: int) -> None:
        repo = KnowledgeBaseRepository(db)
        entity = repo.get_by_id(kb_id)
        if entity is None:
            raise ValueError("Knowledge base not found")

        _, total = KnowledgeFileRepository(db).list_by_kb_paginated(kb_id=kb_id, page=1, page_size=1)
        if total > 0:
            raise ValueError("Please delete files in this knowledge base before deleting it")

        repo.soft_delete(entity)
        self.ensure_default_kb(db)


knowledge_service = KnowledgeService()
