from __future__ import annotations

import json
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from core.config import settings
from repositories.text2sql_schema_annotation_repo import Text2SQLSchemaAnnotationRepository
from schemas.text2sql import Text2SQLSchemaResponse
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.sql_dialect import default_port_for
from services.text2sql.text_tokens import build_search_tokens


class Text2SQLSchemaService:
    """Read live database schema for routing, SQL generation, and validation."""

    def __init__(self, connection_service: Text2SQLConnectionService):
        self.connection_service = connection_service

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        text = (value or "").strip().strip("`").strip('"').strip("[")
        if text.endswith("]"):
            text = text[:-1]
        if "." in text:
            text = text.split(".")[-1]
        return text.lower()

    @staticmethod
    def _safe_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _safe_load_aliases(cls, raw_value: Any) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, (list, tuple, set)):
            return [cls._safe_text(item) for item in raw_value if cls._safe_text(item)]
        text_value = cls._safe_text(raw_value)
        if not text_value:
            return []
        try:
            parsed = json.loads(text_value)
        except json.JSONDecodeError:
            return [item.strip() for item in text_value.split(",") if item.strip()]
        if isinstance(parsed, list):
            return [cls._safe_text(item) for item in parsed if cls._safe_text(item)]
        if isinstance(parsed, str) and parsed.strip():
            return [parsed.strip()]
        return []

    @staticmethod
    def _normalize_key_part(value: Any) -> str:
        return str(value or "").strip().lower()

    def _resolve_connection_key(self, db: Session) -> str:
        provider = getattr(self.connection_service, "get_public_connection", None)
        if not callable(provider):
            return "unconfigured"
        connection = provider(db)
        if not bool(getattr(connection, "configured", False)):
            return "unconfigured"
        db_type = str(getattr(connection, "db_type", "") or "sqlserver")
        return "|".join(
            [
                self._normalize_key_part(db_type),
                self._normalize_key_part(getattr(connection, "host", "")),
                str(int(getattr(connection, "port", None) or default_port_for(db_type))),
                self._normalize_key_part(getattr(connection, "database", "")),
                self._normalize_key_part(getattr(connection, "db_schema", "")),
                self._normalize_key_part(getattr(connection, "username", "")),
            ]
        )

    @staticmethod
    def _system_table_exists(db: Session, table_name: str) -> bool:
        try:
            bind = db.get_bind()
            return bool(inspect(bind).has_table(table_name))
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _get_queryable_object_names(inspector, schema: str | None = None) -> list[str]:
        names: list[str] = []
        try:
            names.extend(inspector.get_table_names(schema=schema))
        except Exception:  # noqa: BLE001
            pass
        try:
            names.extend(inspector.get_view_names(schema=schema))
        except Exception:  # noqa: BLE001
            pass
        seen: set[str] = set()
        result: list[str] = []
        for name in names:
            safe_name = str(name or "").strip()
            if not safe_name:
                continue
            key = safe_name.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(safe_name)
        return sorted(result)

    def _load_annotation_overlay(
        self,
        db: Session,
        table_names: list[str],
    ) -> dict[str, dict]:
        overlay: dict[str, dict] = {"tables": {}, "columns": {}}
        if not table_names or not self._system_table_exists(db, "text2sql_schema_annotation"):
            return overlay
        try:
            connection_key = self._resolve_connection_key(db)
            rows = Text2SQLSchemaAnnotationRepository(db).list_by_connection_and_tables(
                connection_key=connection_key,
                table_names=table_names,
            )
        except Exception:  # noqa: BLE001
            return overlay

        for row in rows:
            table_name = self._safe_text(getattr(row, "table_name", ""))
            table_key = self._normalize_identifier(table_name)
            if not table_key:
                continue
            table_comment = self._safe_text(getattr(row, "table_comment", ""))
            if table_comment:
                overlay["tables"].setdefault(table_key, {})["table_comment"] = table_comment

            column_name = self._safe_text(getattr(row, "column_name", ""))
            column_key = self._normalize_identifier(column_name)
            if not column_key:
                continue
            overlay["columns"][(table_key, column_key)] = {
                "column_comment": self._safe_text(getattr(row, "column_comment", "")),
                "aliases": self._safe_load_aliases(getattr(row, "aliases", None)),
            }
        return overlay

    def _resolve_active_schema(self, db: Session) -> str | None:
        provider = getattr(self.connection_service, "get_active_schema", None)
        if not callable(provider):
            return None
        try:
            schema = provider(db)
        except Exception:  # noqa: BLE001
            return None
        schema = str(schema or "").strip()
        return schema or None

    @classmethod
    def _normalize_queryable_columns_map(
        cls,
        queryable_columns_map: dict[str, set[str]] | None,
    ) -> dict[str, set[str]]:
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
    def _extract_table_comment(cls, inspector, table_name: str, schema: str | None = None) -> str:
        try:
            payload = inspector.get_table_comment(table_name, schema=schema)
        except Exception:  # noqa: BLE001
            return ""
        if isinstance(payload, dict):
            return cls._safe_text(payload.get("text") or payload.get("comment"))
        return cls._safe_text(payload)

    @classmethod
    def _extract_column_comment(cls, payload: dict[str, Any]) -> str:
        return cls._safe_text(payload.get("comment"))

    @classmethod
    def _extract_primary_key_columns(cls, inspector, table_name: str, schema: str | None = None) -> set[str]:
        try:
            payload = inspector.get_pk_constraint(table_name, schema=schema) or {}
        except Exception:  # noqa: BLE001
            return set()
        raw_columns = payload.get("constrained_columns") if isinstance(payload, dict) else []
        primary_keys: set[str] = set()
        for raw_name in raw_columns or []:
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
            if real_name in seen:
                continue
            seen.add(real_name)
            resolved_tables.append(real_name)
        return resolved_tables, missing_tables

    def list_schema_overview(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> Text2SQLSchemaResponse:
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        active_schema = self._resolve_active_schema(db)
        all_tables = self._get_queryable_object_names(inspector, schema=active_schema)
        resolved_tables, missing_tables = self._resolve_target_tables(all_tables, table_names)
        if table_names and missing_tables:
            raise ValueError(f"以下表在数据库中不存在: {', '.join(missing_tables)}")

        normalized_queryable_map = self._normalize_queryable_columns_map(queryable_columns_map)
        annotation_overlay = self._load_annotation_overlay(db, resolved_tables)
        tables: list[dict[str, Any]] = []
        for table_name in resolved_tables:
            normalized_table = self._normalize_identifier(table_name)
            allowed_columns = normalized_queryable_map.get(normalized_table)
            table_annotation = annotation_overlay["tables"].get(normalized_table, {})
            table_comment = (
                self._safe_text(table_annotation.get("table_comment"))
                or self._extract_table_comment(inspector, table_name, active_schema)
            )
            column_items: list[dict[str, Any]] = []
            for col in inspector.get_columns(table_name, schema=active_schema):
                column_name = self._safe_text(col.get("name"))
                if not column_name:
                    continue
                normalized_column = self._normalize_identifier(column_name)
                if allowed_columns is not None and normalized_column not in allowed_columns:
                    continue
                column_annotation = annotation_overlay["columns"].get((normalized_table, normalized_column), {})
                column_comment = (
                    self._safe_text(column_annotation.get("column_comment"))
                    or self._extract_column_comment(col)
                )
                column_items.append(
                    {
                        "name": column_name,
                        "type": self._safe_text(col.get("type")),
                        "comment": column_comment,
                        "aliases": list(column_annotation.get("aliases") or []),
                    }
                )

            tables.append(
                {
                    "table_name": table_name,
                    "table_comment": table_comment,
                    "columns": column_items,
                }
            )
        return Text2SQLSchemaResponse(tables=tables)

    def list_table_options(self, db: Session) -> list[dict[str, str]]:
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        active_schema = self._resolve_active_schema(db)
        table_names = self._get_queryable_object_names(inspector, schema=active_schema)
        annotation_overlay = self._load_annotation_overlay(db, table_names)
        return [
            {
                "table_name": table_name,
                "table_comment": (
                    self._safe_text(
                        annotation_overlay["tables"]
                        .get(self._normalize_identifier(table_name), {})
                        .get("table_comment")
                    )
                    or self._extract_table_comment(inspector, table_name, active_schema)
                ),
            }
            for table_name in table_names
        ]

    def list_table_options_by_names(self, db: Session, table_names: list[str]) -> list[dict[str, str]]:
        if not table_names:
            return []
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        active_schema = self._resolve_active_schema(db)
        all_tables = self._get_queryable_object_names(inspector, schema=active_schema)
        resolved_tables, missing_tables = self._resolve_target_tables(all_tables, table_names)
        if missing_tables:
            raise ValueError(f"以下表在数据库中不存在: {', '.join(missing_tables)}")
        annotation_overlay = self._load_annotation_overlay(db, resolved_tables)
        return [
            {
                "table_name": table_name,
                "table_comment": (
                    self._safe_text(
                        annotation_overlay["tables"]
                        .get(self._normalize_identifier(table_name), {})
                        .get("table_comment")
                    )
                    or self._extract_table_comment(inspector, table_name, active_schema)
                ),
            }
            for table_name in resolved_tables
        ]

    def get_table_detail(
        self,
        db: Session,
        table_name: str,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> dict[str, Any]:
        schema = self.list_schema_overview(
            db,
            table_names=[table_name],
            queryable_columns_map=queryable_columns_map,
        )
        if not schema.tables:
            raise ValueError(f"以下表在数据库中不存在: {table_name}")
        return schema.tables[0].model_dump()

    def list_table_names(self, db: Session) -> list[str]:
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        active_schema = self._resolve_active_schema(db)
        return self._get_queryable_object_names(inspector, schema=active_schema)

    def validate_selected_tables(self, db: Session, table_names: list[str] | None) -> tuple[list[str], list[str]]:
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        active_schema = self._resolve_active_schema(db)
        return self._resolve_target_tables(self._get_queryable_object_names(inspector, schema=active_schema), table_names)

    def get_live_table_column_metadata(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        active_schema = self._resolve_active_schema(db)
        all_tables = self._get_queryable_object_names(inspector, schema=active_schema)
        resolved_tables, missing_tables = self._resolve_target_tables(all_tables, table_names)
        if table_names and missing_tables:
            raise ValueError(f"以下表在数据库中不存在: {', '.join(missing_tables)}")

        normalized_queryable_map = self._normalize_queryable_columns_map(queryable_columns_map)
        annotation_overlay = self._load_annotation_overlay(db, resolved_tables)
        metadata: dict[str, list[dict[str, Any]]] = {}
        for table_name in resolved_tables:
            normalized_table = self._normalize_identifier(table_name)
            allowed_columns = normalized_queryable_map.get(normalized_table)
            primary_keys = self._extract_primary_key_columns(inspector, table_name, active_schema)
            column_items: list[dict[str, Any]] = []
            for column in inspector.get_columns(table_name, schema=active_schema):
                column_name = self._safe_text(column.get("name"))
                if not column_name:
                    continue
                normalized_column = self._normalize_identifier(column_name)
                if allowed_columns is not None and normalized_column not in allowed_columns:
                    continue
                column_annotation = annotation_overlay["columns"].get((normalized_table, normalized_column), {})
                column_items.append(
                    {
                        "name": column_name,
                        "type": self._safe_text(column.get("type")),
                        "comment": (
                            self._safe_text(column_annotation.get("column_comment"))
                            or self._extract_column_comment(column)
                        ),
                        "aliases": list(column_annotation.get("aliases") or []),
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
        schema = self.list_schema_overview(
            db,
            table_names=table_names,
            queryable_columns_map=queryable_columns_map,
        )
        return {table.table_name: {col.name for col in table.columns} for table in schema.tables}

    def get_column_semantic_map(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        schema = self.list_schema_overview(
            db,
            table_names=table_names,
            queryable_columns_map=queryable_columns_map,
        )
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for table in schema.tables:
            column_map: dict[str, dict[str, Any]] = {}
            for column in table.columns:
                column_map[column.name] = {
                    "table_name": table.table_name,
                    "table_comment": table.table_comment,
                    "column_name": column.name,
                    "column_comment": column.comment,
                    "aliases": list(column.aliases or []),
                }
            result[table.table_name] = column_map
        return result

    @staticmethod
    def _pick_best_comment_match(matches: list[dict[str, str]]) -> dict[str, str]:
        if not matches:
            return {}
        ranked = sorted(
            matches,
            key=lambda item: (
                bool(str(item.get("column_comment") or "").strip()),
                bool(str(item.get("table_comment") or "").strip()),
                str(item.get("table_name") or ""),
                str(item.get("column_name") or ""),
            ),
            reverse=True,
        )
        return ranked[0]

    def build_query_field_comment_bindings(
        self,
        db: Session,
        columns: list[str],
        table_names: list[str] | None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> list[dict[str, Any]]:
        """把查询结果字段映射到数据库表/字段注释，供前端展示字段语义。"""
        if not columns:
            return []

        normalized_tables = [str(table).strip() for table in (table_names or []) if str(table).strip()]
        schema_lookup: dict[str, list[dict[str, str]]] = {}
        if normalized_tables:
            try:
                schema = self.list_schema_overview(
                    db,
                    table_names=normalized_tables,
                    queryable_columns_map=queryable_columns_map,
                )
                for table in schema.tables:
                    table_name = str(table.table_name or "")
                    table_comment = str(table.table_comment or "")
                    for column in table.columns:
                        column_name = str(column.name or "")
                        if not column_name:
                            continue
                        normalized_column = self._normalize_identifier(column_name)
                        if not normalized_column:
                            continue
                        schema_lookup.setdefault(normalized_column, []).append(
                            {
                                "table_name": table_name,
                                "table_comment": table_comment,
                                "column_name": column_name,
                                "column_comment": str(column.comment or ""),
                            }
                        )
            except Exception:  # noqa: BLE001
                schema_lookup = {}

        bindings: list[dict[str, Any]] = []
        for raw_column in columns:
            column = str(raw_column or "").strip()
            if not column:
                continue
            normalized_column = self._normalize_identifier(column)
            matches = schema_lookup.get(normalized_column, [])
            chosen = self._pick_best_comment_match(matches)

            table_name = str(chosen.get("table_name") or "")
            table_comment = str(chosen.get("table_comment") or "")
            source_column = str(chosen.get("column_name") or column)
            column_comment = str(chosen.get("column_comment") or "")
            inferred_meaning = column_comment or table_comment or column
            confidence = 1.0 if (column_comment or table_comment) else 0.0

            if matches and len(matches) > 1:
                candidate_tables = "、".join(
                    sorted({str(item.get("table_name") or "") for item in matches if str(item.get("table_name") or "")})
                )
                reason = f"字段在多个表命中（{candidate_tables}），按注释完整度绑定到 {table_name}.{source_column}"
            elif matches:
                reason = f"已绑定数据库注释：{table_name}.{source_column}"
            else:
                reason = "未命中数据库字段注释，返回字段原名"

            bindings.append(
                {
                    "column": column,
                    "inferred_meaning": inferred_meaning,
                    "confidence": confidence,
                    "reason": reason,
                    "table_name": table_name,
                    "table_comment": table_comment,
                    "column_name": source_column,
                    "column_comment": column_comment,
                }
            )
        return bindings

    def build_live_schema_json(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
        question: str | None = None,
    ) -> str:
        schema = self.list_schema_overview(
            db,
            table_names=table_names,
            queryable_columns_map=queryable_columns_map,
        )
        question_text = str(question or "").strip()
        prune_enabled = bool(settings.TEXT2SQL_SCHEMA_PRUNE_ENABLED) and bool(question_text)
        max_cols_per_table = max(1, int(settings.TEXT2SQL_SCHEMA_MAX_COLS_PER_TABLE or 1))
        keep_cols = max(1, int(settings.TEXT2SQL_SCHEMA_PRUNE_KEEP_COLS or 1))
        question_tokens = build_search_tokens(question_text, max_tokens=320) if prune_enabled else set()

        tables_payload: list[dict[str, Any]] = []
        for table in schema.tables:
            columns_payload = []
            for col in table.columns:
                column_payload = {
                    "name": col.name,
                    "type": str(col.type or ""),
                    "comment": str(col.comment or ""),
                }
                if col.aliases:
                    column_payload["aliases"] = list(col.aliases)
                columns_payload.append(column_payload)
            if prune_enabled and len(columns_payload) > max_cols_per_table:
                columns_payload = self._prune_columns(columns_payload, question_tokens, keep_cols)
            tables_payload.append(
                {
                    "table_name": table.table_name,
                    "table_comment": table.table_comment,
                    "columns": columns_payload,
                }
            )
        return json.dumps({"tables": tables_payload}, ensure_ascii=False)

    @staticmethod
    def _column_display_priority(column: dict[str, Any]) -> int:
        """给适合展示给用户看的业务字段一个稳定优先级。"""
        name = str(column.get("name") or "").strip().lower()
        comment = str(column.get("comment") or "").strip().lower()
        aliases = " ".join(str(item or "").strip().lower() for item in column.get("aliases") or [])
        text = f"{name} {comment} {aliases}"
        if any(token in text for token in ("password", "passwd", "secret", "token", "salt", "hash", "密钥", "密码")):
            return -10
        if any(token in text for token in ("name", "title", "姓名", "名称", "名字", "标题", "display", "label")):
            return 8
        if any(token in text for token in ("account", "number", "code", "no", "编号", "学号", "工号", "账号", "代码")):
            return 6
        if any(token in text for token in ("class", "grade", "dept", "major", "班级", "年级", "部门", "学院", "专业")):
            return 5
        if any(token in text for token in ("status", "state", "type", "category", "状态", "类型", "类别", "分类")):
            return 4
        if any(token in text for token in ("date", "time", "year", "semester", "created", "updated", "日期", "时间", "学年", "学期")):
            return 3
        if any(token in text for token in ("score", "amount", "money", "count", "分数", "成绩", "金额", "数量")):
            return 2
        if name == "id" or name.endswith("_id"):
            return 1
        return 0

    @classmethod
    def _prune_columns(
        cls,
        columns_payload: list[dict[str, Any]],
        question_tokens: set[str],
        keep_cols: int,
    ) -> list[dict[str, Any]]:
        scored: list[tuple[int, int, int, str, dict[str, Any]]] = []
        for column in columns_payload:
            column_name = str(column.get("name") or "")
            column_comment = str(column.get("comment") or "")
            aliases_text = " ".join(str(item or "") for item in column.get("aliases") or [])
            column_tokens = build_search_tokens(f"{column_name} {column_comment} {aliases_text}", max_tokens=128)
            overlap = len(column_tokens.intersection(question_tokens))
            has_comment = 1 if column_comment.strip() else 0
            display_priority = cls._column_display_priority(column)
            scored.append((overlap, display_priority, has_comment, column_name, column))
        scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
        kept = [item[4] for item in scored[:keep_cols]]
        omitted_count = max(0, len(columns_payload) - len(kept))
        if omitted_count > 0:
            kept.append(
                {
                    "name": f"... 省略 {omitted_count} 列",
                    "type": "schema_pruned",
                    "comment": "schema_pruned_for_prompt",
                }
            )
        return kept
