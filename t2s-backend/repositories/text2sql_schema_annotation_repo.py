from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from models.text2sql_schema_annotation import Text2SQLSchemaAnnotation


class Text2SQLSchemaAnnotationRepository:
    """Persistence helpers for schema annotation overlay records."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _dump_aliases(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        if isinstance(value, (list, tuple, set)):
            aliases = [cls._clean_text(item) for item in value if cls._clean_text(item)]
            return json.dumps(aliases, ensure_ascii=False) if aliases else None
        return json.dumps([cls._clean_text(value)], ensure_ascii=False)

    def list_by_connection_and_tables(
        self,
        *,
        connection_key: str,
        table_names: list[str],
    ) -> list[Text2SQLSchemaAnnotation]:
        safe_tables = [self._clean_text(item) for item in table_names if self._clean_text(item)]
        if not safe_tables:
            return []
        return (
            self.db.query(Text2SQLSchemaAnnotation)
            .filter(
                Text2SQLSchemaAnnotation.connection_key == connection_key,
                Text2SQLSchemaAnnotation.table_name.in_(safe_tables),
            )
            .all()
        )

    def upsert_many(self, items: list[dict[str, Any]]) -> list[Text2SQLSchemaAnnotation]:
        records: list[Text2SQLSchemaAnnotation] = []
        for item in items:
            connection_key = self._clean_text(item.get("connection_key"))
            table_name = self._clean_text(item.get("table_name"))
            column_name = self._clean_text(item.get("column_name"))
            if not connection_key or not table_name:
                continue

            record = (
                self.db.query(Text2SQLSchemaAnnotation)
                .filter(
                    Text2SQLSchemaAnnotation.connection_key == connection_key,
                    Text2SQLSchemaAnnotation.table_name == table_name,
                    Text2SQLSchemaAnnotation.column_name == column_name,
                )
                .first()
            )
            if record is None:
                record = Text2SQLSchemaAnnotation(
                    connection_key=connection_key,
                    table_name=table_name,
                    column_name=column_name,
                )
                self.db.add(record)

            if "table_comment" in item:
                record.table_comment = self._clean_text(item.get("table_comment")) or None
            if "column_comment" in item:
                record.column_comment = self._clean_text(item.get("column_comment")) or None
            if "aliases" in item:
                record.aliases = self._dump_aliases(item.get("aliases"))
            records.append(record)

        self.db.flush()
        return records
