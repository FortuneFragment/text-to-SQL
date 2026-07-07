from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from core.knowledge_usage import normalize_kb_usage
from models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    _usage_column_checked: bool = False
    _usage_column_available: bool = True

    def __init__(self, db: Session):
        self.db = db

    def ensure_usage_column(self) -> bool:
        cls = self.__class__
        if cls._usage_column_checked:
            return cls._usage_column_available

        cls._usage_column_checked = True
        cls._usage_column_available = True
        try:
            bind = self.db.get_bind()
            inspector = inspect(bind)
            columns = {
                str(column.get("name") or "").lower()
                for column in inspector.get_columns(KnowledgeBase.__tablename__)
            }
            if "usage_type" in columns:
                return True

            ddl = (
                "ALTER TABLE knowledge_base "
                "ADD COLUMN usage_type VARCHAR(32) NOT NULL DEFAULT 'table_route'"
            )
            self.db.execute(text(ddl))
            self.db.commit()
            return True
        except Exception:  # noqa: BLE001
            self.db.rollback()
            cls._usage_column_available = False
            return False

    def get_by_id(self, kb_id: int) -> KnowledgeBase | None:
        self.ensure_usage_column()
        return (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def get_by_id_for_usage(self, kb_id: int, usage: str) -> KnowledgeBase | None:
        self.ensure_usage_column()
        return (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.usage == normalize_kb_usage(usage),
                KnowledgeBase.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def list_all(self) -> list[KnowledgeBase]:
        self.ensure_usage_column()
        return (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.is_deleted == False)  # noqa: E712
            .order_by(KnowledgeBase.usage.asc(), KnowledgeBase.is_default.desc(), KnowledgeBase.id.asc())
            .all()
        )

    def list_by_usage(self, usage: str) -> list[KnowledgeBase]:
        self.ensure_usage_column()
        return (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.usage == normalize_kb_usage(usage),
                KnowledgeBase.is_deleted == False,  # noqa: E712
            )
            .order_by(KnowledgeBase.is_default.desc(), KnowledgeBase.id.asc())
            .all()
        )

    def get_default(self, usage: str | None = None) -> KnowledgeBase | None:
        self.ensure_usage_column()
        query = self.db.query(KnowledgeBase).filter(
            KnowledgeBase.is_default == True,  # noqa: E712
            KnowledgeBase.is_deleted == False,  # noqa: E712
        )
        if usage is not None:
            query = query.filter(KnowledgeBase.usage == normalize_kb_usage(usage))
        return (
            query
            .order_by(KnowledgeBase.id.asc())
            .first()
        )

    def create(self, entity: KnowledgeBase) -> KnowledgeBase:
        self.ensure_usage_column()
        entity.usage = normalize_kb_usage(getattr(entity, "usage", None))
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: KnowledgeBase) -> KnowledgeBase:
        self.ensure_usage_column()
        entity.usage = normalize_kb_usage(getattr(entity, "usage", None))
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def clear_default_flag(self) -> None:
        self.ensure_usage_column()
        (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.is_deleted == False)  # noqa: E712
            .update({KnowledgeBase.is_default: False}, synchronize_session=False)
        )
        self.db.commit()

    def soft_delete(self, entity: KnowledgeBase) -> None:
        self.ensure_usage_column()
        entity.is_deleted = True
        if entity.is_default:
            entity.is_default = False
        entity.name = f"{entity.name}__deleted_{entity.id}"
        entity.collection_name = f"{entity.collection_name}__deleted_{entity.id}"
        self.db.add(entity)
        self.db.commit()
