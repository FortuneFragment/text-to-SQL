from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import inspect

from core.knowledge_policy import parse_usage, KnowledgeUsage
from core.domain_errors import (
    KnowledgeBaseNotFoundError,
    KnowledgeUsageImmutableError,
    KnowledgeUsageMismatchError,
)
from models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, kb_id: int) -> KnowledgeBase | None:
        return (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.id == kb_id)
            .first()
        )

    def get_by_id_for_usages(self, kb_id: int, usages: list[str] | list[KnowledgeUsage]) -> KnowledgeBase | None:
        normalized_usages = [parse_usage(u).value for u in usages]
        return (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.usage.in_(normalized_usages),
            )
            .first()
        )

    def require_by_id_for_usages(self, kb_id: int, usages: list[str] | list[KnowledgeUsage]) -> KnowledgeBase:
        kb = self.get_by_id(kb_id)
        if kb is None:
            raise KnowledgeBaseNotFoundError(f"Knowledge base ID {kb_id} not found")

        normalized_usages = [parse_usage(u).value for u in usages]
        if kb.usage not in normalized_usages:
            raise KnowledgeUsageMismatchError(
                f"Knowledge base ID {kb_id} usage '{kb.usage}' does not match expected: {normalized_usages}"
            )
        return kb

    def get_by_id_for_usage(self, kb_id: int, usage: str) -> KnowledgeBase | None:
        return self.get_by_id_for_usages(kb_id, [usage])

    def list_all(self) -> list[KnowledgeBase]:
        return (
            self.db.query(KnowledgeBase)
            .order_by(KnowledgeBase.usage.asc(), KnowledgeBase.id.asc())
            .all()
        )

    def list_by_usage(self, usage: str) -> list[KnowledgeBase]:
        u = parse_usage(usage).value
        return (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.usage == u,
            )
            .order_by(KnowledgeBase.id.asc())
            .all()
        )

    def lock_by_id(self, kb_id: int) -> KnowledgeBase | None:
        return (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.id == kb_id)
            .with_for_update()
            .first()
        )

    def create(self, entity: KnowledgeBase) -> KnowledgeBase:
        entity.usage = parse_usage(getattr(entity, "usage", None)).value
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: KnowledgeBase) -> KnowledgeBase:
        normalized_usage = parse_usage(
            getattr(entity, "usage", None)
        ).value
        state = inspect(entity)
        usage_history = state.attrs.usage.history
        if usage_history.has_changes() and usage_history.deleted:
            previous_usage = parse_usage(
                usage_history.deleted[0]
            ).value
            if previous_usage != normalized_usage:
                raise KnowledgeUsageImmutableError(
                    "不允许修改已有知识库用途"
                )

        entity.usage = normalized_usage
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity: KnowledgeBase) -> None:
        self.db.delete(entity)
        self.db.commit()
