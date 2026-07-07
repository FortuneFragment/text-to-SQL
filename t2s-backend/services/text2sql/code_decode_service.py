"""Text2SQL 码值解码服务（查询后，按 TEXT2SQL_CODE_DECODE_ENABLED 开关启用）。

对结果集中已登记字段绑定的编码列，用码值字典把 code 替换成中文（替换原值）。
结果列名按物理列名匹配绑定；多表同名列绑定到不同类目时无法确定归属，保守跳过不解，避免错解。
解码不改 SQL、不产生 JOIN（与「JOIN 只来自 FK+vo」约束正交）；任何异常安全返回原始 rows。
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

from sqlalchemy.orm import Session

from core.config import settings
from repositories.text2sql_code_dict_binding_repo import Text2SQLCodeDictBindingRepository
from repositories.text2sql_code_dict_value_repo import Text2SQLCodeDictValueRepository


class Text2SQLCodeDecodeService:
    def __init__(self, connection_key_provider: Callable[[Session], str]):
        self._connection_key_provider = connection_key_provider
        self._logger = logging.getLogger("text2sql.console")

    def decode_rows(
        self,
        *,
        db: Session,
        candidate_tables: list[str],
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not rows or not columns:
            return list(rows or [])
        try:
            max_rows = max(1, int(getattr(settings, "TEXT2SQL_CODE_DECODE_MAX_ROWS", 2000)))
            if len(rows) > max_rows:
                return list(rows)  # 结果过大，跳过解码（性能保护）

            connection_key = self._connection_key_provider(db)
            if not connection_key or connection_key == "unconfigured":
                return list(rows)

            bindings = Text2SQLCodeDictBindingRepository(db).list_active_by_tables(
                connection_key, list(candidate_tables or [])
            )
            if not bindings:
                return list(rows)

            # 列名 → 类目；多表同名列绑定不一致则丢弃，避免错解。
            column_to_categories: dict[str, set[str]] = defaultdict(set)
            for binding in bindings:
                if binding.category_key:
                    column_to_categories[binding.column_name.upper()].add(binding.category_key)
            column_to_category = {
                column: next(iter(categories))
                for column, categories in column_to_categories.items()
                if len(categories) == 1
            }
            if not column_to_category:
                return list(rows)

            # 结果列（保留原列名/别名）→ 类目。
            decode_columns: dict[Any, str] = {}
            for column in columns:
                category_key = column_to_category.get(str(column).upper())
                if category_key:
                    decode_columns[column] = category_key
            if not decode_columns:
                return list(rows)

            categories = sorted(set(decode_columns.values()))
            codes: set[str] = set()
            for row in rows:
                for column in decode_columns:
                    value = row.get(column)
                    if value is not None and str(value).strip():
                        codes.add(str(value).strip())
            if not codes:
                return list(rows)

            value_rows = Text2SQLCodeDictValueRepository(db).fetch_names(
                connection_key, categories, sorted(codes)
            )
            code_name = {(item.category_key, item.code): item.name for item in value_rows if item.name}
            if not code_name:
                return list(rows)

            decoded: list[dict[str, Any]] = []
            for row in rows:
                new_row = dict(row)
                for column, category_key in decode_columns.items():
                    value = new_row.get(column)
                    if value is None:
                        continue
                    name = code_name.get((category_key, str(value).strip()))
                    if name:
                        new_row[column] = name  # 替换原值
                decoded.append(new_row)
            return decoded
        except Exception:  # noqa: BLE001
            self._logger.exception("[code_decode] failed, return raw rows")
            return list(rows)
