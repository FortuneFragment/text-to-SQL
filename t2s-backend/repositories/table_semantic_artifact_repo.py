from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from core.knowledge_policy import ProcessorType
from core.knowledge_usage import (
    KB_USAGE_TABLE_SEMANTIC_TREE,
)
from models.knowledge_base import KnowledgeBase
from models.knowledge_file import KnowledgeFile
from models.table_semantic_artifact import (
    TableSemanticArtifact,
)


class TableSemanticArtifactRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, entity: TableSemanticArtifact) -> TableSemanticArtifact:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: TableSemanticArtifact) -> TableSemanticArtifact:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def get_by_table_id(self, table_id: str) -> TableSemanticArtifact | None:
        return (
            self.db.query(TableSemanticArtifact)
            .filter(
                TableSemanticArtifact.table_id == str(table_id),
                TableSemanticArtifact.deleted_at.is_(None),
            )
            .first()
        )

    def get_by_file_id(self, file_id: int) -> TableSemanticArtifact | None:
        return (
            self.db.query(TableSemanticArtifact)
            .filter(
                TableSemanticArtifact.file_id == int(file_id),
                TableSemanticArtifact.deleted_at.is_(None),
            )
            .first()
        )

    def list_by_file_id(self, file_id: int, limit: int = 50) -> list[TableSemanticArtifact]:
        safe_limit = max(1, min(int(limit), 200))
        return (
            self.db.query(TableSemanticArtifact)
            .filter(
                TableSemanticArtifact.file_id == int(file_id),
                TableSemanticArtifact.deleted_at.is_(None),
            )
            .order_by(TableSemanticArtifact.created_at.desc(), TableSemanticArtifact.id.desc())
            .limit(safe_limit)
            .all()
        )

    def list_by_kb(self, kb_id: int, limit: int = 50) -> list[TableSemanticArtifact]:
        safe_limit = max(1, min(int(limit), 200))
        return (
            self.db.query(TableSemanticArtifact)
            .filter(
                TableSemanticArtifact.kb_id == int(kb_id),
                TableSemanticArtifact.deleted_at.is_(None),
            )
            .order_by(TableSemanticArtifact.created_at.desc(), TableSemanticArtifact.id.desc())
            .limit(safe_limit)
            .all()
        )

    def list_recent(self, limit: int = 50) -> list[TableSemanticArtifact]:
        safe_limit = max(1, min(int(limit), 200))
        return (
            self.db.query(TableSemanticArtifact)
            .filter(TableSemanticArtifact.deleted_at.is_(None))
            .order_by(TableSemanticArtifact.created_at.desc(), TableSemanticArtifact.id.desc())
            .limit(safe_limit)
            .all()
        )

    def soft_delete_by_file_id(self, file_id: int) -> None:
        (
            self.db.query(TableSemanticArtifact)
            .filter(
                TableSemanticArtifact.file_id == int(file_id),
                TableSemanticArtifact.deleted_at.is_(None),
            )
            .update({TableSemanticArtifact.deleted_at: datetime.utcnow()}, synchronize_session=False)
        )
        self.db.commit()

    def get_any_by_table_id(
        self,
        table_id: str,
    ) -> TableSemanticArtifact | None:
        return (
            self.db.query(TableSemanticArtifact)
            .filter(
                TableSemanticArtifact.table_id
                == str(table_id)
            )
            .first()
        )

    def get_with_context(
        self,
        table_id: str,
    ) -> tuple[
        TableSemanticArtifact,
        KnowledgeFile,
        KnowledgeBase,
    ] | None:
        return (
            self.db.query(
                TableSemanticArtifact,
                KnowledgeFile,
                KnowledgeBase,
            )
            .join(
                KnowledgeFile,
                TableSemanticArtifact.file_id
                == KnowledgeFile.id,
            )
            .join(
                KnowledgeBase,
                TableSemanticArtifact.kb_id
                == KnowledgeBase.id,
            )
            .filter(
                TableSemanticArtifact.table_id
                == str(table_id),
                TableSemanticArtifact.deleted_at.is_(None),

                TableSemanticArtifact.usage_snapshot
                == KB_USAGE_TABLE_SEMANTIC_TREE,

                KnowledgeFile.id
                == TableSemanticArtifact.file_id,
                KnowledgeFile.kb_id
                == TableSemanticArtifact.kb_id,
                KnowledgeFile.is_deleted
                == False,  # noqa: E712
                KnowledgeFile.usage_snapshot
                == KB_USAGE_TABLE_SEMANTIC_TREE,
                KnowledgeFile.processor_type
                == ProcessorType.TABLE_SEMANTIC.value,

                KnowledgeBase.id
                == TableSemanticArtifact.kb_id,
                KnowledgeBase.usage
                == KB_USAGE_TABLE_SEMANTIC_TREE,
            )
            .first()
        )

    def list_valid_by_kb_ids(
        self,
        *,
        kb_ids: list[int],
        limit: int = 50,
    ) -> list[TableSemanticArtifact]:
        normalized_kb_ids = [
            int(kb_id)
            for kb_id in kb_ids
            if int(kb_id) > 0
        ]

        if not normalized_kb_ids:
            return []

        safe_limit = max(
            1,
            min(int(limit), 200),
        )

        return (
            self.db.query(TableSemanticArtifact)
            .join(
                KnowledgeFile,
                TableSemanticArtifact.file_id
                == KnowledgeFile.id,
            )
            .join(
                KnowledgeBase,
                TableSemanticArtifact.kb_id
                == KnowledgeBase.id,
            )
            .filter(
                TableSemanticArtifact.kb_id.in_(
                    normalized_kb_ids
                ),
                TableSemanticArtifact.deleted_at.is_(None),
                TableSemanticArtifact.usage_snapshot
                == KB_USAGE_TABLE_SEMANTIC_TREE,

                KnowledgeFile.id
                == TableSemanticArtifact.file_id,
                KnowledgeFile.kb_id
                == TableSemanticArtifact.kb_id,
                KnowledgeFile.is_deleted
                == False,  # noqa: E712
                KnowledgeFile.usage_snapshot
                == KB_USAGE_TABLE_SEMANTIC_TREE,
                KnowledgeFile.processor_type
                == ProcessorType.TABLE_SEMANTIC.value,

                KnowledgeBase.id
                == TableSemanticArtifact.kb_id,
                KnowledgeBase.usage
                == KB_USAGE_TABLE_SEMANTIC_TREE,
            )
            .order_by(
                TableSemanticArtifact.created_at.desc(),
                TableSemanticArtifact.id.desc(),
            )
            .limit(safe_limit)
            .all()
        )

    def list_valid_by_file_id(
        self,
        *,
        file_id: int,
        limit: int = 200,
    ) -> list[TableSemanticArtifact]:
        safe_limit = max(
            1,
            min(int(limit), 500),
        )

        return (
            self.db.query(TableSemanticArtifact)
            .join(
                KnowledgeFile,
                TableSemanticArtifact.file_id
                == KnowledgeFile.id,
            )
            .join(
                KnowledgeBase,
                TableSemanticArtifact.kb_id
                == KnowledgeBase.id,
            )
            .filter(
                TableSemanticArtifact.file_id
                == int(file_id),
                TableSemanticArtifact.deleted_at.is_(None),
                TableSemanticArtifact.usage_snapshot
                == KB_USAGE_TABLE_SEMANTIC_TREE,

                KnowledgeFile.id == int(file_id),
                KnowledgeFile.kb_id
                == TableSemanticArtifact.kb_id,
                KnowledgeFile.is_deleted
                == False,  # noqa: E712
                KnowledgeFile.usage_snapshot
                == KB_USAGE_TABLE_SEMANTIC_TREE,
                KnowledgeFile.processor_type
                == ProcessorType.TABLE_SEMANTIC.value,

                KnowledgeBase.id
                == TableSemanticArtifact.kb_id,
                KnowledgeBase.usage
                == KB_USAGE_TABLE_SEMANTIC_TREE,
            )
            .order_by(
                TableSemanticArtifact.created_at.asc(),
                TableSemanticArtifact.id.asc(),
            )
            .limit(safe_limit)
            .all()
        )

    def soft_delete_by_file_context(
        self,
        *,
        file_id: int,
        kb_id: int,
    ) -> int:
        updated = (
            self.db.query(TableSemanticArtifact)
            .filter(
                TableSemanticArtifact.file_id
                == int(file_id),
                TableSemanticArtifact.kb_id
                == int(kb_id),
                TableSemanticArtifact.usage_snapshot
                == KB_USAGE_TABLE_SEMANTIC_TREE,
                TableSemanticArtifact.deleted_at.is_(None),
            )
            .update(
                {
                    TableSemanticArtifact.deleted_at:
                        datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )

        self.db.commit()

        return int(updated)

    def upsert(
        self,
        entity: TableSemanticArtifact,
    ) -> TableSemanticArtifact:
        existing = (
            self.db.query(TableSemanticArtifact)
            .filter(
                TableSemanticArtifact.table_id
                == str(entity.table_id)
            )
            .first()
        )

        if existing is None:
            self.db.add(entity)
            self.db.commit()
            self.db.refresh(entity)
            return entity

        if (
            int(existing.file_id)
            != int(entity.file_id)
            or int(existing.kb_id)
            != int(entity.kb_id)
        ):
            raise ValueError(
                "Existing table_id belongs to another "
                "file or knowledge base"
            )

        existing.usage_snapshot = (
            entity.usage_snapshot
        )
        existing.file_name = entity.file_name
        existing.sheet_name = entity.sheet_name
        existing.table_title = entity.table_title
        existing.summary_text = entity.summary_text

        existing.candidate_fields_json = (
            entity.candidate_fields_json
        )
        existing.tree_path_text_json = (
            entity.tree_path_text_json
        )
        existing.tree_metric_names_json = (
            entity.tree_metric_names_json
        )

        existing.tree_object_name = (
            entity.tree_object_name
        )
        existing.row_count = entity.row_count
        existing.column_count = entity.column_count

        # 重处理成功后恢复为有效产物。
        existing.deleted_at = None

        self.db.add(existing)
        self.db.commit()
        self.db.refresh(existing)

        return existing
