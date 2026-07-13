from __future__ import annotations

import json
from typing import Any, Iterable

from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from core.knowledge_policy import KnowledgeUsage, parse_usage
from models.document_chunk import DocumentChunk
from models.knowledge_file import KnowledgeFile
from models.knowledge_base import KnowledgeBase


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

    def get_by_task_id(
        self,
        task_id: str,
    ) -> KnowledgeFile | None:
        normalized_task_id = str(
            task_id or ""
        ).strip()

        if not normalized_task_id:
            return None

        return (
            self.db.query(KnowledgeFile)
            .filter(
                KnowledgeFile.task_id
                == normalized_task_id,
                KnowledgeFile.is_deleted
                == False,  # noqa: E712
            )
            .first()
        )

    def get_with_kb(self, file_id: int) -> tuple[KnowledgeFile, KnowledgeBase] | None:
        row = (
            self.db.query(KnowledgeFile, KnowledgeBase)
            .join(KnowledgeBase, KnowledgeFile.kb_id == KnowledgeBase.id)
            .filter(
                KnowledgeFile.id == file_id,
                KnowledgeFile.is_deleted == False,
            )
            .first()
        )
        return row

    def get_with_kb_for_usages(
        self,
        file_id: int,
        usages: list[str] | list[KnowledgeUsage],
    ) -> tuple[KnowledgeFile, KnowledgeBase] | None:
        normalized = [parse_usage(u).value for u in usages]
        row = (
            self.db.query(KnowledgeFile, KnowledgeBase)
            .join(KnowledgeBase, KnowledgeFile.kb_id == KnowledgeBase.id)
            .filter(
                KnowledgeFile.id == file_id,
                KnowledgeFile.is_deleted == False,
                KnowledgeBase.usage.in_(normalized),
            )
            .first()
        )
        return row

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

    def list_by_kb_context_paginated(
            self,
            *,
            kb_id: int,
            usage_snapshot: str,
            processor_type: str,
            page: int,
            page_size: int,
    ) -> tuple[list[KnowledgeFile], int]:
        query = self.db.query(KnowledgeFile).filter(
            KnowledgeFile.kb_id == int(kb_id),
            KnowledgeFile.usage_snapshot == str(usage_snapshot),
            KnowledgeFile.processor_type == str(processor_type),
            KnowledgeFile.is_deleted == False,  # noqa: E712
        )

        total = query.count()

        rows = (
            query.order_by(
                KnowledgeFile.created_at.desc(),
                KnowledgeFile.id.desc(),
            )
            .offset((int(page) - 1) * int(page_size))
            .limit(int(page_size))
            .all()
        )

        return rows, int(total)

    def check_exists_by_md5_in_context(
            self,
            *,
            kb_id: int,
            md5: str,
            usage_snapshot: str,
            processor_type: str,
    ) -> bool:
        return (
                self.db.query(KnowledgeFile.id)
                .filter(
                    KnowledgeFile.kb_id == int(kb_id),
                    KnowledgeFile.md5 == str(md5),
                    KnowledgeFile.usage_snapshot
                    == str(usage_snapshot),
                    KnowledgeFile.processor_type
                    == str(processor_type),
                    KnowledgeFile.is_deleted == False,  # noqa: E712
                )
                .first()
                is not None
        )

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

    def submit_task(
            self,
            file_id: int,
            task_id: str,
    ) -> int:
        """原子增加处理版本，并绑定新的 Celery task_id。"""

        normalized_task_id = str(task_id or "").strip()

        if not normalized_task_id:
            raise ValueError("task_id cannot be empty")

        file_entity = (
            self.db.query(KnowledgeFile)
            .filter(
                KnowledgeFile.id == int(file_id),
                KnowledgeFile.is_deleted == False,
            )
            .with_for_update()
            .first()
        )

        if file_entity is None:
            raise ValueError("File not found")

        current_version = int(
            file_entity.process_version or 0
        )

        new_version = current_version + 1

        file_entity.process_version = new_version
        file_entity.task_id = normalized_task_id
        file_entity.status = 0
        file_entity.error_msg = None
        file_entity.table_task_meta_json = None

        self.db.add(file_entity)
        self.db.commit()
        self.db.refresh(file_entity)

        return new_version

    def update_status(
        self,
        file_id: int,
        *,
        status: int,
        error_msg: str | None = None,
        task_id: str | None = None,
        process_version: int | None = None,
    ) -> bool:
        query = self.db.query(KnowledgeFile).filter(KnowledgeFile.id == file_id)
        if process_version is not None:
            query = query.filter(KnowledgeFile.process_version == process_version)

        payload: dict = {
            KnowledgeFile.status: status,
            KnowledgeFile.error_msg: error_msg,
        }
        if task_id is not None:
            payload[KnowledgeFile.task_id] = task_id

        updated = query.update(payload, synchronize_session=False)
        self.db.commit()
        return updated > 0

    def update_status_for_task(
            self,
            file_id: int,
            *,
            task_id: str,
            process_version: int,
            status: int,
            error_msg: str | None = None,
    ) -> bool:
        """只允许当前 task_id 和 process_version 更新文件状态。"""

        normalized_task_id = str(task_id or "").strip()

        if not normalized_task_id:
            return False

        updated = (
            self.db.query(KnowledgeFile)
            .filter(
                KnowledgeFile.id == int(file_id),
                KnowledgeFile.task_id == normalized_task_id,
                KnowledgeFile.process_version
                == int(process_version),
                KnowledgeFile.is_deleted == False,  # noqa: E712
            )
            .update(
                {
                    KnowledgeFile.status: int(status),
                    KnowledgeFile.error_msg: error_msg,
                },
                synchronize_session=False,
            )
        )

        self.db.commit()

        return updated > 0

    def update_table_task_meta_for_task(
        self,
        file_id: int,
        *,
        task_id: str,
        process_version: int,
        task_meta: dict[str, Any],
    ) -> bool:
        normalized_task_id = str(
            task_id or ""
        ).strip()

        if not normalized_task_id:
            return False

        serialized = json.dumps(
            task_meta,
            ensure_ascii=False,
            default=str,
        )

        updated = (
            self.db.query(KnowledgeFile)
            .filter(
                KnowledgeFile.id == int(file_id),
                KnowledgeFile.task_id
                == normalized_task_id,
                KnowledgeFile.process_version
                == int(process_version),
                KnowledgeFile.is_deleted
                == False,  # noqa: E712
            )
            .update(
                {
                    KnowledgeFile
                    .table_task_meta_json: serialized,
                },
                synchronize_session=False,
            )
        )

        self.db.commit()

        return updated > 0

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

    def delete_chunks_by_file_id(self, file_id: int, kb_id: int | None = None, usage_snapshot: str | None = None) -> None:
        query = delete(DocumentChunk).where(DocumentChunk.file_id == file_id)
        if kb_id is not None:
            query = query.where(DocumentChunk.kb_id == kb_id)
        if usage_snapshot is not None:
            query = query.where(DocumentChunk.usage_snapshot == usage_snapshot)
        self.db.execute(query)
        self.db.commit()

    def list_chunks_by_file_paginated(
            self,
            file_id: int,
            page: int,
            page_size: int,
            kb_id: int | None = None,
            usage_snapshot: str | None = None,
            processor_type: str | None = None,
    ) -> tuple[list[DocumentChunk], int]:
        query = self.db.query(DocumentChunk).filter(
            DocumentChunk.file_id == int(file_id)
        )

        if kb_id is not None:
            query = query.filter(
                DocumentChunk.kb_id == int(kb_id)
            )

        if usage_snapshot is not None:
            query = query.filter(
                DocumentChunk.usage_snapshot
                == str(usage_snapshot)
            )

        if processor_type is not None:
            query = query.filter(
                DocumentChunk.processor_type
                == str(processor_type)
            )

        total = query.count()

        rows = (
            query.order_by(
                DocumentChunk.chunk_index.asc(),
                DocumentChunk.id.asc(),
            )
            .offset((int(page) - 1) * int(page_size))
            .limit(int(page_size))
            .all()
        )

        return rows, int(total)

    def count_chunks_by_file_id(
            self,
            file_id: int,
            kb_id: int | None = None,
            usage_snapshot: str | None = None,
            processor_type: str | None = None,
    ) -> int:
        query = self.db.query(
            func.count(DocumentChunk.id)
        ).filter(
            DocumentChunk.file_id == int(file_id)
        )

        if kb_id is not None:
            query = query.filter(
                DocumentChunk.kb_id == int(kb_id)
            )

        if usage_snapshot is not None:
            query = query.filter(
                DocumentChunk.usage_snapshot
                == str(usage_snapshot)
            )

        if processor_type is not None:
            query = query.filter(
                DocumentChunk.processor_type
                == str(processor_type)
            )

        return int(query.scalar() or 0)

    def count_chunks_by_file_ids(
            self,
            *,
            file_ids: list[int],
            kb_id: int,
            usage_snapshot: str,
            processor_type: str,
    ) -> dict[int, int]:
        normalized_file_ids = [
            int(file_id)
            for file_id in file_ids
            if int(file_id) > 0
        ]

        if not normalized_file_ids:
            return {}

        rows = (
            self.db.query(
                DocumentChunk.file_id,
                func.count(DocumentChunk.id),
            )
            .filter(
                DocumentChunk.file_id.in_(
                    normalized_file_ids
                ),
                DocumentChunk.kb_id == int(kb_id),
                DocumentChunk.usage_snapshot
                == str(usage_snapshot),
                DocumentChunk.processor_type
                == str(processor_type),
            )
            .group_by(DocumentChunk.file_id)
            .all()
        )

        return {
            int(file_id): int(count)
            for file_id, count in rows
        }

    def get_chunks_by_ids(self, chunk_ids: Iterable[int]) -> list[DocumentChunk]:
        chunk_ids = list(chunk_ids)
        if not chunk_ids:
            return []
        return self.db.query(DocumentChunk).filter(DocumentChunk.id.in_(chunk_ids)).all()
