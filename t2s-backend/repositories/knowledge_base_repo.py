from __future__ import annotations

from sqlalchemy.orm import Session

from models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, kb_id: int) -> KnowledgeBase | None:
        return (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def list_all(self) -> list[KnowledgeBase]:
        return (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.is_deleted == False)  # noqa: E712
            .order_by(KnowledgeBase.is_default.desc(), KnowledgeBase.id.asc())
            .all()
        )

    def get_default(self) -> KnowledgeBase | None:
        return (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.is_default == True,  # noqa: E712
                KnowledgeBase.is_deleted == False,  # noqa: E712
            )
            .order_by(KnowledgeBase.id.asc())
            .first()
        )

    def create(self, entity: KnowledgeBase) -> KnowledgeBase:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: KnowledgeBase) -> KnowledgeBase:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def clear_default_flag(self) -> None:
        (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.is_deleted == False)  # noqa: E712
            .update({KnowledgeBase.is_default: False}, synchronize_session=False)
        )
        self.db.commit()

    def soft_delete(self, entity: KnowledgeBase) -> None:
        entity.is_deleted = True
        if entity.is_default:
            entity.is_default = False
        entity.name = f"{entity.name}__deleted_{entity.id}"
        entity.collection_name = f"{entity.collection_name}__deleted_{entity.id}"
        self.db.add(entity)
        self.db.commit()
