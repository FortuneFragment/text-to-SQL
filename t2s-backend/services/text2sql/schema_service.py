from __future__ import annotations

import json
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from schemas.text2sql import Text2SQLSchemaResponse
from services.text2sql.connection_service import Text2SQLConnectionService

class Text2SQLSchemaService:
    """读取数据库真实 Schema，并提供表字段查询能力。"""
    def __init__(self, connection_service: Text2SQLConnectionService):
        """初始化 Schema 服务并注入连接服务。"""
        self.connection_service = connection_service

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        """把标识符标准化为可比较的形式。"""
        text = (value or "").strip().strip("`").strip('"')
        if "." in text:
            text = text.split(".")[-1]
        return text.lower()

    @staticmethod
    def _safe_text(value: Any) -> str:
        """将任意值安全转成字符串。"""
        return str(value or "").strip()

    @classmethod
    def _normalize_queryable_columns_map(
        cls,
        queryable_columns_map: dict[str, set[str]] | None,
    ) -> dict[str, set[str]]:
        """标准化字段权限映射，统一表名和字段名格式。"""
        normalized: dict[str, set[str]] = {}
        for table_name, columns in (queryable_columns_map or {}).items():
            normalized_table = cls._normalize_identifier(table_name)
            if not normalized_table:
                continue
            normalized[normalized_table] = {
                cls._normalize_identifier(column_name)
                for column_name in (columns or set())
                if cls._normalize_identifier(column_name)
            }
        return normalized

    @classmethod
    def _extract_table_comment(cls, inspector, table_name: str) -> str:
        """读取表注释，失败时返回空字符串。"""
        try:
            payload = inspector.get_table_comment(table_name)
        except Exception:  # noqa: BLE001
            return ""
        if isinstance(payload, dict):
            return cls._safe_text(payload.get("text") or payload.get("comment"))
        return cls._safe_text(payload)

    @classmethod
    def _extract_column_comment(cls, payload: dict[str, Any]) -> str:
        """从字段元数据中提取注释。"""
        return cls._safe_text(payload.get("comment"))

    @classmethod
    def _extract_primary_key_columns(cls, inspector, table_name: str) -> set[str]:
        """读取主键字段名集合。"""
        try:
            payload = inspector.get_pk_constraint(table_name) or {}
        except Exception:  # noqa: BLE001
            return set()
        raw_columns = payload.get("constrained_columns") if isinstance(payload, dict) else []
        primary_keys: set[str] = set()
        for raw_name in (raw_columns or []):
            normalized = cls._normalize_identifier(cls._safe_text(raw_name))
            if normalized:
                primary_keys.add(normalized)
        return primary_keys

    @classmethod
    def _resolve_target_tables(
        cls,
        all_tables: list[str],
        table_names: list[str] | None,
    ) -> tuple[list[str], list[str]]:
        """把输入表名映射为真实表名，并返回缺失表名。"""
        if table_names is None:
            return sorted(all_tables), []
        if len(table_names) == 0:
            return [], []
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

    def list_schema_overview(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> Text2SQLSchemaResponse:
        """返回数据库表结构概览，包含字段类型和注释。"""
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        resolved_tables, missing_tables = self._resolve_target_tables(all_tables, table_names)
        if table_names and missing_tables:
            raise ValueError(f"以下表在数据库中不存在: {', '.join(missing_tables)}")
        normalized_queryable_map = self._normalize_queryable_columns_map(queryable_columns_map)
        tables: list[dict[str, Any]] = []
        for table_name in resolved_tables:
            normalized_table = self._normalize_identifier(table_name)
            allowed_columns = normalized_queryable_map.get(normalized_table)
            columns = inspector.get_columns(table_name)
            column_items: list[dict[str, str]] = []
            for col in columns:
                column_name = self._safe_text(col.get("name"))
                if not column_name:
                    continue
                normalized_column = self._normalize_identifier(column_name)
                if allowed_columns is not None and normalized_column not in allowed_columns:
                    continue
                column_items.append(
                    {
                        "name": column_name,
                        "type": self._safe_text(col.get("type")),
                        "comment": self._extract_column_comment(col),
                    }
                )

            tables.append(
                {
                    "table_name": table_name,
                    "table_comment": self._extract_table_comment(inspector, table_name),
                    "columns": column_items,
                    }
                )
        return Text2SQLSchemaResponse(tables=tables)

    def list_table_options(self, db: Session) -> list[dict[str, str]]:
        """返回表开关页面需要的表名与表注释列表。"""
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        table_names = sorted(inspector.get_table_names())
        return [
            {
                "table_name": table_name,
                "table_comment": self._extract_table_comment(inspector, table_name),
            }
            for table_name in table_names
        ]

    def get_table_detail(
        self,
        db: Session,
        table_name: str,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> dict[str, Any]:
        """返回单张表的详细字段信息。"""
        schema = self.list_schema_overview(
            db,
            table_names=[table_name],
            queryable_columns_map=queryable_columns_map,
        )
        if not schema.tables:
            raise ValueError(f"以下表在数据库中不存在: {table_name}")
        return schema.tables[0].model_dump()

    def list_table_names(self, db: Session) -> list[str]:
        """返回当前数据库中的所有表名。"""
        return [item["table_name"] for item in self.list_table_options(db)]

    def validate_selected_tables(self, db: Session, table_names: list[str] | None) -> tuple[list[str], list[str]]:
        """校验表名列表，返回可用表与不存在表。"""
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        return self._resolve_target_tables(inspector.get_table_names(), table_names)

    def get_live_table_column_metadata(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """返回实时字段元数据，包含类型和主键标记。"""
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        resolved_tables, missing_tables = self._resolve_target_tables(all_tables, table_names)
        if table_names and missing_tables:
            raise ValueError(f"以下表在数据库中不存在: {', '.join(missing_tables)}")
        normalized_queryable_map = self._normalize_queryable_columns_map(queryable_columns_map)
        metadata: dict[str, list[dict[str, Any]]] = {}
        for table_name in resolved_tables:
            normalized_table = self._normalize_identifier(table_name)
            allowed_columns = normalized_queryable_map.get(normalized_table)
            primary_keys = self._extract_primary_key_columns(inspector, table_name)
            column_items: list[dict[str, Any]] = []

            for column in inspector.get_columns(table_name):
                column_name = self._safe_text(column.get("name"))
                if not column_name:
                    continue
                normalized_column = self._normalize_identifier(column_name)
                if allowed_columns is not None and normalized_column not in allowed_columns:
                    continue

                column_items.append(
                    {
                        "name": column_name,
                        "type": self._safe_text(column.get("type")),
                        "is_primary_key": normalized_column in primary_keys,
                    }
                )
            metadata[table_name] = column_items
        return metadata

    def get_live_table_columns_map(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> dict[str, set[str]]:
        """返回每张表对应的可查询字段集合。"""
        schema = self.list_schema_overview(
            db,
            table_names=table_names,
            queryable_columns_map=queryable_columns_map,
        )
        mapping: dict[str, set[str]] = {}
        for table in schema.tables:
            mapping[table.table_name] = {col.name for col in table.columns}
        return mapping

    def build_live_schema_json(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> str:
        """把实时 Schema 压缩为 JSON 文本，供 LLM 提示词使用。"""
        schema = self.list_schema_overview(
            db,
            table_names=table_names,
            queryable_columns_map=queryable_columns_map,
        )
        payload = {
            "tables": [
                {
                    "table_name": table.table_name,
                    "table_comment": table.table_comment,
                    "columns": [
                        {
                            "name": col.name,
                            "type": str(col.type or ""),
                            "comment": str(col.comment or ""),
                        }
                        for col in table.columns
                    ],
                }
                for table in schema.tables
            ]
        }
        return json.dumps(payload, ensure_ascii=False)
