from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.text2sql_table_relation import Text2SQLTableRelation


class Text2SQLTableRelationRepository:
    """负责表关系配置的持久化。"""

    def __init__(self, db: Session):
        self.db = db

    def list_by_user_and_connection(
        self,
        *,
        user_id: int,
        connection_key: str,
        keyword: str | None = None,
        table_name: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Text2SQLTableRelation], int]:
        query = self.db.query(Text2SQLTableRelation).filter(
            Text2SQLTableRelation.user_id == user_id,
            Text2SQLTableRelation.connection_key == connection_key,
        )
        safe_keyword = str(keyword or "").strip().lower()
        if safe_keyword:
            pattern = f"%{safe_keyword}%"
            query = query.filter(
                or_(
                    Text2SQLTableRelation.source_table.ilike(pattern),
                    Text2SQLTableRelation.target_table.ilike(pattern),
                    Text2SQLTableRelation.description.ilike(pattern),
                )
            )
        safe_table_name = str(table_name or "").strip()
        if safe_table_name:
            query = query.filter(
                or_(
                    Text2SQLTableRelation.source_table == safe_table_name,
                    Text2SQLTableRelation.target_table == safe_table_name,
                )
            )
        total = int(query.count())
        safe_page = max(1, int(page))
        safe_page_size = max(1, int(page_size))
        rows = (
            query.order_by(
                Text2SQLTableRelation.updated_at.desc(),
                Text2SQLTableRelation.id.desc(),
            )
            .offset((safe_page - 1) * safe_page_size)
            .limit(safe_page_size)
            .all()
        )
        return rows, total

    def get_by_id(self, relation_id: int) -> Text2SQLTableRelation | None:
        return self.db.query(Text2SQLTableRelation).filter(Text2SQLTableRelation.id == relation_id).first()

    def create(self, payload: dict) -> Text2SQLTableRelation:
        relation = Text2SQLTableRelation(**payload)
        self.db.add(relation)
        self.db.commit()
        self.db.refresh(relation)
        return relation

    def update(self, relation: Text2SQLTableRelation, payload: dict) -> Text2SQLTableRelation:
        for key, value in payload.items():
            setattr(relation, key, value)
        self.db.commit()
        self.db.refresh(relation)
        return relation

    def delete(self, relation: Text2SQLTableRelation) -> None:
        self.db.delete(relation)
        self.db.commit()

    def list_by_tables(
        self,
        *,
        user_id: int,
        connection_key: str,
        table_names: list[str],
    ) -> list[Text2SQLTableRelation]:
        if not table_names:
            return []
        return (
            self.db.query(Text2SQLTableRelation)
            .filter(
                Text2SQLTableRelation.user_id == user_id,
                Text2SQLTableRelation.connection_key == connection_key,
                Text2SQLTableRelation.source_table.in_(table_names),
                Text2SQLTableRelation.target_table.in_(table_names),
            )
            .all()
        )

    def list_by_pair(
        self,
        *,
        user_id: int,
        connection_key: str,
        source_table: str,
        target_table: str,
        exclude_id: int | None = None,
    ) -> list[Text2SQLTableRelation]:
        query = self.db.query(Text2SQLTableRelation).filter(
            Text2SQLTableRelation.user_id == user_id,
            Text2SQLTableRelation.connection_key == connection_key,
            or_(
                (
                    (Text2SQLTableRelation.source_table == source_table)
                    & (Text2SQLTableRelation.target_table == target_table)
                ),
                (
                    (Text2SQLTableRelation.source_table == target_table)
                    & (Text2SQLTableRelation.target_table == source_table)
                ),
            ),
        )
        if exclude_id is not None:
            query = query.filter(Text2SQLTableRelation.id != int(exclude_id))
        return query.all()
