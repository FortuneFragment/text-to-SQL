from __future__ import annotations

from typing import Iterable

from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from models.document_chunk import DocumentChunk
from models.knowledge_file import KnowledgeFile


class KnowledgeFileRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_file(self, entity: KnowledgeFile) -> KnowledgeFile:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def get_by_id(self, file_id: int) -> KnowledgeFile | None:
        return (
            self.db.query(KnowledgeFile)
            .filter(
                KnowledgeFile.id == file_id,
                KnowledgeFile.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def list_by_kb_paginated(self, kb_id: int, page: int, page_size: int) -> tuple[list[KnowledgeFile], int]:
        query = self.db.query(KnowledgeFile).filter(
            KnowledgeFile.kb_id == kb_id,
            KnowledgeFile.is_deleted == False,  # noqa: E712
        )
        total = query.count()
        rows = (
            query.order_by(KnowledgeFile.created_at.desc(), KnowledgeFile.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return rows, total

    def check_exists_by_md5(self, kb_id: int, md5: str) -> bool:
        return (
            self.db.query(KnowledgeFile.id)
            .filter(
                KnowledgeFile.kb_id == kb_id,
                KnowledgeFile.md5 == md5,
                KnowledgeFile.is_deleted == False,  # noqa: E712
            )
            .first()
            is not None
        )

    def update_status(
        self,
        file_id: int,
        *,
        status: int,
        error_msg: str | None = None,
        task_id: str | None = None,
    ) -> None:
        payload: dict = {
            KnowledgeFile.status: status,
            KnowledgeFile.error_msg: error_msg,
        }
        if task_id is not None:
            payload[KnowledgeFile.task_id] = task_id

        (
            self.db.query(KnowledgeFile)
            .filter(KnowledgeFile.id == file_id)
            .update(payload, synchronize_session=False)
        )
        self.db.commit()

    def set_task_id(self, file_id: int, task_id: str | None) -> None:
        (
            self.db.query(KnowledgeFile)
            .filter(KnowledgeFile.id == file_id)
            .update({KnowledgeFile.task_id: task_id}, synchronize_session=False)
        )
        self.db.commit()

    def update_strategy(self, entity: KnowledgeFile, chunk_size: int, chunk_overlap: int) -> KnowledgeFile:
        entity.custom_chunk_size = chunk_size
        entity.custom_chunk_overlap = chunk_overlap
        entity.status = 0
        entity.error_msg = None
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def soft_delete(self, entity: KnowledgeFile) -> None:
        entity.is_deleted = True
        self.db.add(entity)
        self.db.commit()

    def bulk_create_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        self.db.add_all(chunks)
        self.db.commit()
        for item in chunks:
            self.db.refresh(item)
        return chunks

    def delete_chunks_by_file_id(self, file_id: int) -> None:
        self.db.execute(delete(DocumentChunk).where(DocumentChunk.file_id == file_id))
        self.db.commit()

    def list_chunks_by_file_paginated(
        self,
        file_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[DocumentChunk], int]:
        query = self.db.query(DocumentChunk).filter(DocumentChunk.file_id == file_id)
        total = query.count()
        rows = (
            query.order_by(DocumentChunk.chunk_index.asc(), DocumentChunk.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return rows, total

    def count_chunks_by_file_id(self, file_id: int) -> int:
        return (
            self.db.query(func.count(DocumentChunk.id))
            .filter(DocumentChunk.file_id == file_id)
            .scalar()
            or 0
        )

    def get_chunks_by_ids(self, chunk_ids: Iterable[int]) -> list[DocumentChunk]:
        chunk_ids = list(chunk_ids)
        if not chunk_ids:
            return []
        return self.db.query(DocumentChunk).filter(DocumentChunk.id.in_(chunk_ids)).all()
