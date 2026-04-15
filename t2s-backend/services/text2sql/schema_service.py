from __future__ import annotations

import json
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from schemas.text2sql import Text2SQLSchemaResponse
from services.text2sql.connection_service import Text2SQLConnectionService


class Text2SQLSchemaService:
    """中文备注：封装Schema 信息处理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(self, connection_service: Text2SQLConnectionService):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self.connection_service`。
        self.connection_service = connection_service

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        """中文备注：规范化identifier相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `text`。
        text = (value or "").strip().strip("`").strip('"')
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if "." in text:
            text = text.split(".")[-1]
        # 3. 返回结果：输出当前函数最终结果。
        return text.lower()

    @staticmethod
    def _safe_text(value: Any) -> str:
        """中文备注：处理text相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return str(value or "").strip()

    @classmethod
    def _normalize_queryable_columns_map(
        cls,
        queryable_columns_map: dict[str, set[str]] | None,
    ) -> dict[str, set[str]]:
        """中文备注：规范化queryable columns map相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        normalized: dict[str, set[str]] = {}
        # 2. 迭代处理：遍历集合并逐项构建结果。
        for table_name, columns in (queryable_columns_map or {}).items():
            normalized_table = cls._normalize_identifier(table_name)
            if not normalized_table:
                continue
            normalized[normalized_table] = {
                cls._normalize_identifier(column_name)
                for column_name in (columns or set())
                if cls._normalize_identifier(column_name)
            }
        # 3. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        return normalized

    @classmethod
    def _extract_table_comment(cls, inspector, table_name: str) -> str:
        """中文备注：提取table comment相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 核心处理：执行当前阶段的业务逻辑。
        try:
            payload = inspector.get_table_comment(table_name)
        except Exception:  # noqa: BLE001
            return ""
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if isinstance(payload, dict):
            return cls._safe_text(payload.get("text") or payload.get("comment"))
        # 3. 返回结果：输出当前函数最终结果。
        return cls._safe_text(payload)

    @classmethod
    def _extract_column_comment(cls, payload: dict[str, Any]) -> str:
        """中文备注：提取column comment相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return cls._safe_text(payload.get("comment"))

    @classmethod
    def _resolve_target_tables(
        cls,
        all_tables: list[str],
        table_names: list[str] | None,
    ) -> tuple[list[str], list[str]]:
        """中文备注：解析target tables相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if table_names is None:
            return sorted(all_tables), []

        # 2. 条件分支：根据当前状态选择不同处理路径。
        if len(table_names) == 0:
            return [], []

        # 3. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        table_lookup = {cls._normalize_identifier(name): name for name in all_tables}
        resolved_tables: list[str] = []
        missing_tables: list[str] = []
        seen: set[str] = set()

        # 4. 迭代处理：遍历集合并逐项构建结果。
        for raw_name in table_names:
            normalized = cls._normalize_identifier(raw_name)
            real_name = table_lookup.get(normalized)
            if not real_name:
                missing_tables.append(str(raw_name))
                continue
            if real_name not in seen:
                resolved_tables.append(real_name)
                seen.add(real_name)

        # 5. 目标解析与合法性校验：解析输入范围并拦截非法数据。
        return resolved_tables, missing_tables

    def list_schema_overview(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> Text2SQLSchemaResponse:
        """获取数据库 Schema 的全局概览，提取表名、列名、字段类型和业务注释。
        执行流程：初始化反射能力 -> 解析目标表 -> 执行字段级剪枝 -> 返回结构化 Schema。
        """
        # 1. 引擎与反射机制初始化：获取数据库连接引擎并创建 Inspector，用于后续元数据反射。
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        resolved_tables, missing_tables = self._resolve_target_tables(all_tables, table_names)

        # 2. 目标表解析与合法性校验：比对传入表名与物理库真实表名，阻断非法表输入。
        if table_names and missing_tables:
            raise ValueError(f"以下表在数据库中不存在: {', '.join(missing_tables)}")

        # 3. 字段白名单标准化：统一表名/列名标识符格式，确保后续列权限匹配准确。
        normalized_queryable_map = self._normalize_queryable_columns_map(queryable_columns_map)
        tables: list[dict[str, Any]] = []

        # 4. 遍历解析表级结构：逐表提取基础元数据并准备列级信息容器。
        for table_name in resolved_tables:
            normalized_table = self._normalize_identifier(table_name)
            allowed_columns = normalized_queryable_map.get(normalized_table)
            columns = inspector.get_columns(table_name)
            column_items: list[dict[str, str]] = []

            # 5. 遍历解析列级结构并执行 Schema 剪枝：仅保留允许暴露给模型的列。
            for col in columns:
                column_name = self._safe_text(col.get("name"))
                if not column_name:
                    continue
                normalized_column = self._normalize_identifier(column_name)
                if allowed_columns is not None and normalized_column not in allowed_columns:
                    continue

                # 6. 组装列元数据：提取列名、字段类型和字段注释，供 SQL 生成阶段使用。
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

        # 7. 组装响应对象：返回结构化 Schema，供 Prompt 构造和表路由逻辑复用。
        return Text2SQLSchemaResponse(tables=tables)

    def list_table_options(self, db: Session) -> list[dict[str, str]]:
        """中文备注：列出table options相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 引擎与反射能力初始化：准备数据库连接和元数据提取能力。
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        table_names = sorted(inspector.get_table_names())
        # 2. 返回结果：输出当前函数最终结果。
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
        """中文备注：获取table detail相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `schema`。
        schema = self.list_schema_overview(
            db,
            table_names=[table_name],
            queryable_columns_map=queryable_columns_map,
        )
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not schema.tables:
            raise ValueError(f"以下表在数据库中不存在: {table_name}")
        # 3. 返回结果：输出当前函数最终结果。
        return schema.tables[0].model_dump()

    def list_table_names(self, db: Session) -> list[str]:
        """中文备注：列出table names相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return [item["table_name"] for item in self.list_table_options(db)]

    def validate_selected_tables(self, db: Session, table_names: list[str] | None) -> tuple[list[str], list[str]]:
        """中文备注：校验selected tables相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 引擎与反射能力初始化：准备数据库连接和元数据提取能力。
        engine = self.connection_service.get_engine(db)
        inspector = inspect(engine)
        # 2. 目标解析与合法性校验：解析输入范围并拦截非法数据。
        return self._resolve_target_tables(inspector.get_table_names(), table_names)

    def get_live_table_columns_map(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> dict[str, set[str]]:
        """中文备注：获取live table columns map相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `schema`。
        schema = self.list_schema_overview(
            db,
            table_names=table_names,
            queryable_columns_map=queryable_columns_map,
        )
        mapping: dict[str, set[str]] = {}
        # 2. 迭代处理：遍历集合并逐项构建结果。
        for table in schema.tables:
            mapping[table.table_name] = {col.name for col in table.columns}
        # 3. 返回结果：输出当前函数最终结果。
        return mapping

    def build_live_schema_json(
        self,
        db: Session,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> str:
        """中文备注：构建live schema json相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `schema`。
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
                    "columns": [col.name for col in table.columns],
                }
                for table in schema.tables
            ]
        }
        # 2. 返回结果：输出当前函数最终结果。
        return json.dumps(payload, ensure_ascii=False)
