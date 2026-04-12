from __future__ import annotations

import json
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from schemas.text2sql import Text2SQLSchemaResponse
from services.text2sql.connection_service import Text2SQLConnectionService


class Text2SQLSchemaService:
    def __init__(self, connection_service: Text2SQLConnectionService):
        self.connection_service = connection_service

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        text = (value or "").strip().strip("`").strip('"')
        if "." in text:
            text = text.split(".")[-1]
        return text.lower()

    @classmethod
    def _resolve_target_tables(
        cls,
        all_tables: list[str],
        table_names: list[str] | None,
    ) -> tuple[list[str], list[str]]:
        if not table_names:
            return sorted(all_tables), []

        table_lookup = {cls._normalize_identifier(name): name for name in all_tables}
        resolved_tables: list[str] = []
        missing_tables: list[str] = []
        seen: set[str] = set()

        for raw_name in table_names:
            normalized = cls._normalize_identifier(raw_name)
            real_name = table_lookup.get(normalized)
            if not real_name:
                missing_tables.append(str(raw_name))
                continue
            if real_name not in seen:
                resolved_tables.append(real_name)
                seen.add(real_name)

        return resolved_tables, missing_tables

    def list_schema_overview(self, db: Session, table_names: list[str] | None = None) -> Text2SQLSchemaResponse:
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        resolved_tables, missing_tables = self._resolve_target_tables(all_tables, table_names)
        if table_names and missing_tables:
            raise ValueError(f"以下表在数据库中不存在: {', '.join(missing_tables)}")

        tables: list[dict[str, Any]] = []
        for table_name in resolved_tables:
            columns = inspector.get_columns(table_name)
            tables.append(
                {
                    "table_name": table_name,
                    "columns": [
                        {
                            "name": str(col["name"]),
                            "type": str(col["type"]),
                        }
                        for col in columns
                        if col.get("name")
                    ],
                }
            )

        return Text2SQLSchemaResponse(tables=tables)

    def list_table_names(self, db: Session) -> list[str]:
        schema = self.list_schema_overview(db)
        return sorted([table.table_name for table in schema.tables])

    def validate_selected_tables(self, db: Session, table_names: list[str] | None) -> tuple[list[str], list[str]]:
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        return self._resolve_target_tables(inspector.get_table_names(), table_names)

    def get_live_table_columns_map(self, db: Session, table_names: list[str] | None = None) -> dict[str, set[str]]:
        schema = self.list_schema_overview(db, table_names)
        mapping: dict[str, set[str]] = {}
        for table in schema.tables:
            mapping[table.table_name] = {col.name for col in table.columns}
        return mapping

    def build_live_schema_json(self, db: Session, table_names: list[str] | None = None) -> str:
        schema = self.list_schema_overview(db, table_names)
        payload = {
            "tables": [
                {
                    "table_name": table.table_name,
                    "columns": [col.name for col in table.columns],
                }
                for table in schema.tables
            ]
        }
        return json.dumps(payload, ensure_ascii=False)
