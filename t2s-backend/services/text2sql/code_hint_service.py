"""Text2SQL 码值编码注入服务（生成前，按 TEXT2SQL_CODE_HINT_ENABLED 开关启用）。

对候选表中已登记字段绑定的编码列，取其字典取值拼成 code_dict_json 注入提示词，
让模型写过滤条件时用真实 code（如 TITLE_ID='011' 而非臆造 '教授'）。

与枚举提示（enum_hint）分工：编码列归本服务（注入 code→中文 映射），自由文本列归 enum_hint；
本服务额外返回编码列集合，供调用方把这些列从 enum_hint 探测中排除（否则只会采样到裸码）。

小字典全量注入；大字典（超阈值，如刊物/学科）按用户问句关键词在中文名上检索子集。
任何异常安全降级为原始提示词，绝不阻断主流程。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Callable

from sqlalchemy.orm import Session

from core.config import settings
from repositories.text2sql_code_dict_binding_repo import Text2SQLCodeDictBindingRepository
from repositories.text2sql_code_dict_value_repo import Text2SQLCodeDictValueRepository


class Text2SQLCodeHintService:
    def __init__(self, connection_key_provider: Callable[[Session], str]):
        self._connection_key_provider = connection_key_provider
        self._logger = logging.getLogger("text2sql.console")

    @staticmethod
    def _extract_keywords(question: str) -> list[str]:
        """从问句粗提关键词（2+ 长度的中文片段或字母数字），用于大字典检索。"""
        words = re.findall(r"[一-鿿]{2,}|[A-Za-z0-9]{2,}", str(question or ""))
        # 去重保序
        seen: set[str] = set()
        result: list[str] = []
        for word in words:
            if word not in seen:
                seen.add(word)
                result.append(word)
        return result[:20]

    def build_prompt_hint(
        self,
        *,
        db: Session,
        candidate_tables: list[str],
        question: str,
        base_prompt_hint: str,
    ) -> tuple[str, set[tuple[str, str]]]:
        """返回 (追加码值块后的提示词, 编码列集合)。编码列集合用于从 enum_hint 排除。"""
        base = str(base_prompt_hint or "")
        try:
            connection_key = self._connection_key_provider(db)
            if not connection_key or connection_key == "unconfigured":
                return base, set()

            bindings = Text2SQLCodeDictBindingRepository(db).list_active_by_tables(
                connection_key, list(candidate_tables or [])
            )
            if not bindings:
                return base, set()

            coded_columns = {(b.table_name.upper(), b.column_name.upper()) for b in bindings}
            category_keys = list({b.category_key for b in bindings if b.category_key})
            if not category_keys:
                return base, coded_columns

            value_repo = Text2SQLCodeDictValueRepository(db)
            small_max = max(1, int(settings.TEXT2SQL_CODE_HINT_SMALL_DICT_MAX))
            per_category = max(1, int(settings.TEXT2SQL_CODE_HINT_MAX_VALUES_PER_CATEGORY))

            counts = value_repo.count_by_categories(connection_key, category_keys)
            small_keys = [key for key in category_keys if 0 < counts.get(key, 0) <= small_max]
            large_keys = [key for key in category_keys if counts.get(key, 0) > small_max]

            category_values: dict[str, list[tuple[str, str]]] = {}
            for value in value_repo.list_by_categories(connection_key, small_keys):
                bucket = category_values.setdefault(value.category_key, [])
                if len(bucket) < per_category:
                    bucket.append((value.code, value.name))

            if large_keys:
                keywords = self._extract_keywords(question)
                searched = value_repo.search_by_keyword(
                    connection_key, large_keys, keywords, limit_per_category=per_category
                )
                for key, rows in searched.items():
                    category_values[key] = [(row.code, row.name) for row in rows]

            payload: dict[str, dict] = {}
            for binding in bindings:
                values = category_values.get(binding.category_key)
                if not values:
                    continue
                payload[f"{binding.table_name}.{binding.column_name}"] = {
                    "category": binding.category_key,
                    "values": {code: name for code, name in values if str(code).strip()},
                }

            if not payload:
                return base, coded_columns

            block = (
                "code_dict_json（编码列的 code→中文 映射；对这些列做 = / IN 过滤时必须用左侧 code 值）:\n"
                + json.dumps(payload, ensure_ascii=False)
            )
            enhanced = f"{base.strip()}\n\n{block}" if base.strip() else block
            self._logger.info(
                "[code_hint] tables=%s coded_columns=%s injected=%s",
                json.dumps(list(candidate_tables or []), ensure_ascii=False),
                len(coded_columns),
                len(payload),
            )
            return enhanced, coded_columns
        except Exception:  # noqa: BLE001
            self._logger.exception("[code_hint] failed, degraded to base hint")
            return base, set()
