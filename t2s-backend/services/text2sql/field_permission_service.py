from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from repositories.text2sql_field_permission_repo import Text2SQLFieldPermissionRepository
from schemas.text2sql import (
    Text2SQLTableFieldItem,
    Text2SQLTableFieldsResponse,
    Text2SQLTableOption,
    Text2SQLTableOptionsResponse,
    UpdateText2SQLTableFieldsRequest,
)
from services.text2sql.config_service import GLOBAL_CONFIG_USER_ID, Text2SQLConfigService
from services.text2sql.schema_service import Text2SQLSchemaService


class Text2SQLFieldPermissionService:
    """中文备注：封装服务层能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(
        self,
        schema_service: Text2SQLSchemaService,
        config_service: Text2SQLConfigService,
    ):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self.schema_service`。
        self.schema_service = schema_service
        self.config_service = config_service

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
    def _normalize_connection_key(value: str | None) -> str:
        """中文备注：规范化connection key相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `text`。
        text = str(value or "").strip()
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if len(text) <= 255:
            return text
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        # 3. 返回结果：输出当前函数最终结果。
        return f"sha256:{digest}"

    def _resolve_table_name(self, db: Session, table_name: str) -> str:
        """中文备注：解析table name相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 目标解析与合法性校验：解析输入范围并拦截非法数据。
        resolved, missing = self.schema_service.validate_selected_tables(db, [table_name])
        # 2. 目标解析与合法性校验：解析输入范围并拦截非法数据。
        if missing or not resolved:
            raise ValueError(f"\u4ee5\u4e0b\u8868\u5728\u6570\u636e\u5e93\u4e2d\u4e0d\u5b58\u5728: {table_name}")
        # 3. 返回结果：输出当前函数最终结果。
        return resolved[0]

    def get_table_options(self, db: Session) -> Text2SQLTableOptionsResponse:
        """中文备注：获取table options相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `options`。
        options = self.schema_service.list_table_options(db)
        # 2. 返回结果：输出当前函数最终结果。
        return Text2SQLTableOptionsResponse(tables=[Text2SQLTableOption(**item) for item in options])

    def get_table_fields(self, db: Session, table_name: str) -> Text2SQLTableFieldsResponse:
        """中文备注：获取table fields相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 目标解析与合法性校验：解析输入范围并拦截非法数据。
        resolved_table = self._resolve_table_name(db, table_name)
        table_detail = self.schema_service.get_table_detail(db, resolved_table)

        # 2. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        connection_key = self._normalize_connection_key(self.config_service.get_connection_key(db))
        records = Text2SQLFieldPermissionRepository(db).list_by_user_and_connection(
            GLOBAL_CONFIG_USER_ID,
            connection_key,
            resolved_table,
        )
        enabled_lookup = {
            self._normalize_identifier(record.column_name): bool(record.query_enabled)
            for record in records
        }

        # 3. 变量构建：计算并更新 `fields: list[Text2SQLTableFieldItem]`。
        fields: list[Text2SQLTableFieldItem] = []
        # 4. 迭代处理：遍历集合并逐项构建结果。
        for column in table_detail.get("columns", []):
            column_name = str(column.get("name") or "")
            if not column_name:
                continue
            fields.append(
                Text2SQLTableFieldItem(
                    name=column_name,
                    type=str(column.get("type") or ""),
                    comment=str(column.get("comment") or ""),
                    query_enabled=enabled_lookup.get(self._normalize_identifier(column_name), True),
                )
            )

        # 5. 返回结果：输出当前函数最终结果。
        return Text2SQLTableFieldsResponse(
            table_name=resolved_table,
            table_comment=str(table_detail.get("table_comment") or ""),
            fields=fields,
        )

    def update_table_fields(
        self,
        db: Session,
        table_name: str,
        request: UpdateText2SQLTableFieldsRequest,
    ) -> Text2SQLTableFieldsResponse:
        """中文备注：更新table fields相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 目标解析与合法性校验：解析输入范围并拦截非法数据。
        resolved_table = self._resolve_table_name(db, table_name)
        table_detail = self.schema_service.get_table_detail(db, resolved_table)

        # 2. 变量构建：计算并更新 `column_name_lookup`。
        column_name_lookup = {
            self._normalize_identifier(str(column.get("name") or "")): str(column.get("name") or "")
            for column in table_detail.get("columns", [])
            if str(column.get("name") or "")
        }
        # 3. 条件分支：根据当前状态选择不同处理路径。
        if not column_name_lookup:
            raise ValueError(f"\u6570\u636e\u8868 {resolved_table} \u6ca1\u6709\u53ef\u914d\u7f6e\u5b57\u6bb5")

        # 4. 变量构建：计算并更新 `incoming_map: dict[str, bool]`。
        incoming_map: dict[str, bool] = {}
        # 5. 迭代处理：遍历集合并逐项构建结果。
        for field in request.fields:
            normalized = self._normalize_identifier(field.name)
            real_name = column_name_lookup.get(normalized)
            if not real_name:
                raise ValueError(f"\u5b57\u6bb5\u4e0d\u5b58\u5728: {field.name}")
            incoming_map[normalized] = bool(field.query_enabled)

        # 6. 变量构建：计算并更新 `permissions: dict[str, bool]`。
        permissions: dict[str, bool] = {}
        # 7. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        for normalized, real_name in column_name_lookup.items():
            permissions[real_name] = incoming_map.get(normalized, True)

        # 8. 条件分支：根据当前状态选择不同处理路径。
        if not any(permissions.values()):
            raise ValueError("\u81f3\u5c11\u4fdd\u7559\u4e00\u4e2a\u53ef\u67e5\u8be2\u5b57\u6bb5")

        # 9. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        connection_key = self._normalize_connection_key(self.config_service.get_connection_key(db))
        Text2SQLFieldPermissionRepository(db).replace_table_permissions(
            user_id=GLOBAL_CONFIG_USER_ID,
            connection_key=connection_key,
            table_name=resolved_table,
            permissions=permissions,
        )
        # 10. 返回结果：输出当前函数最终结果。
        return self.get_table_fields(db, resolved_table)

    def get_queryable_columns_map(
        self,
        db: Session,
        table_names: list[str] | None = None,
    ) -> dict[str, set[str]]:
        """中文备注：获取queryable columns map相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if table_names is None:
            resolved_tables = self.schema_service.list_table_names(db)
        else:
            resolved_tables, _ = self.schema_service.validate_selected_tables(db, table_names)

        # 2. 变量构建：计算并更新 `schema`。
        schema = self.schema_service.list_schema_overview(db, resolved_tables)
        connection_key = self._normalize_connection_key(self.config_service.get_connection_key(db))
        records = Text2SQLFieldPermissionRepository(db).list_by_user_and_connection(
            GLOBAL_CONFIG_USER_ID,
            connection_key,
        )

        # 3. 变量构建：计算并更新 `permission_lookup: dict[str, dict[str, bool]]`。
        permission_lookup: dict[str, dict[str, bool]] = {}
        # 4. 迭代处理：遍历集合并逐项构建结果。
        for record in records:
            normalized_table = self._normalize_identifier(record.table_name)
            normalized_column = self._normalize_identifier(record.column_name)
            permission_lookup.setdefault(normalized_table, {})[normalized_column] = bool(record.query_enabled)

        # 5. 变量构建：计算并更新 `result: dict[str, set[str]]`。
        result: dict[str, set[str]] = {}
        # 6. 迭代处理：遍历集合并逐项构建结果。
        for table in schema.tables:
            normalized_table = self._normalize_identifier(table.table_name)
            table_permission = permission_lookup.get(normalized_table, {})
            enabled_columns: set[str] = set()
            for column in table.columns:
                normalized_column = self._normalize_identifier(column.name)
                if table_permission.get(normalized_column, True):
                    enabled_columns.add(column.name)
            result[table.table_name] = enabled_columns
        # 7. 返回结果：输出当前函数最终结果。
        return result
