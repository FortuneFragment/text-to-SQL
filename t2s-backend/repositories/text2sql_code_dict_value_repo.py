from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models.text2sql_code_dict_value import Text2SQLCodeDictValue


class Text2SQLCodeDictValueRepository:
    """码值字典持久化（按 connection_key 隔离）。

    取值是纯数据，导入用 bulk_replace 整本替换；编码读取按类目全量/关键词检索；
    解码读取按 (category_key, code) 精确命中，避免为几行结果拉回整本大字典。
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _norm_keys(self, category_keys: list[str] | None) -> list[str]:
        return [key for key in (self._clean(item) for item in (category_keys or [])) if key]

    def delete_by_connection(self, connection_key: str) -> int:
        connection_key = self._clean(connection_key)
        if not connection_key:
            return 0
        deleted = (
            self.db.query(Text2SQLCodeDictValue)
            .filter(Text2SQLCodeDictValue.connection_key == connection_key)
            .delete(synchronize_session=False)
        )
        return int(deleted or 0)

    def bulk_replace(self, connection_key: str, items: list[dict[str, Any]]) -> int:
        """整本替换某连接的取值层。取值无人工状态，可安全删后重灌。"""
        connection_key = self._clean(connection_key)
        if not connection_key:
            return 0
        self.delete_by_connection(connection_key)
        records: list[Text2SQLCodeDictValue] = []
        for item in items:
            category_key = self._clean(item.get("category_key"))
            if not category_key:
                continue
            records.append(
                Text2SQLCodeDictValue(
                    connection_key=connection_key,
                    category_key=category_key,
                    code=self._clean(item.get("code")),
                    name=self._clean(item.get("name")),
                )
            )
        if records:
            self.db.bulk_save_objects(records)
        self.db.flush()
        return len(records)

    def count_by_categories(self, connection_key: str, category_keys: list[str]) -> dict[str, int]:
        """每个类目的码值条数，用于编码时判定大/小字典。"""
        connection_key = self._clean(connection_key)
        keys = self._norm_keys(category_keys)
        if not connection_key or not keys:
            return {}
        rows = (
            self.db.query(Text2SQLCodeDictValue.category_key, func.count())
            .filter(
                Text2SQLCodeDictValue.connection_key == connection_key,
                Text2SQLCodeDictValue.category_key.in_(keys),
            )
            .group_by(Text2SQLCodeDictValue.category_key)
            .all()
        )
        return {str(key): int(count) for key, count in rows}

    def list_by_categories(self, connection_key: str, category_keys: list[str]) -> list[Text2SQLCodeDictValue]:
        """按类目全量取值（仅用于小字典；大字典走 search_by_keyword）。"""
        connection_key = self._clean(connection_key)
        keys = self._norm_keys(category_keys)
        if not connection_key or not keys:
            return []
        return (
            self.db.query(Text2SQLCodeDictValue)
            .filter(
                Text2SQLCodeDictValue.connection_key == connection_key,
                Text2SQLCodeDictValue.category_key.in_(keys),
            )
            .order_by(Text2SQLCodeDictValue.category_key, Text2SQLCodeDictValue.code)
            .all()
        )

    def search_by_keyword(
        self,
        connection_key: str,
        category_keys: list[str],
        keywords: list[str],
        *,
        limit_per_category: int = 20,
    ) -> dict[str, list[Text2SQLCodeDictValue]]:
        """大字典关键词检索：在 name 上模糊匹配（兼顾 code 精确），每类目限量返回。"""
        connection_key = self._clean(connection_key)
        keys = self._norm_keys(category_keys)
        words = [word for word in (self._clean(item) for item in (keywords or [])) if word]
        if not connection_key or not keys:
            return {}
        limit = max(1, int(limit_per_category))
        result: dict[str, list[Text2SQLCodeDictValue]] = {}
        for category_key in keys:
            query = self.db.query(Text2SQLCodeDictValue).filter(
                Text2SQLCodeDictValue.connection_key == connection_key,
                Text2SQLCodeDictValue.category_key == category_key,
            )
            if words:
                clauses = [Text2SQLCodeDictValue.name.like(f"%{word}%") for word in words]
                clauses += [Text2SQLCodeDictValue.code == word for word in words]
                query = query.filter(or_(*clauses))
            rows = query.order_by(Text2SQLCodeDictValue.code).limit(limit).all()
            if rows:
                result[category_key] = rows
        return result

    def fetch_names(
        self,
        connection_key: str,
        category_keys: list[str],
        codes: list[str],
    ) -> list[Text2SQLCodeDictValue]:
        """解码用：一次拉回结果集中出现的 (category_key, code) 命中行。"""
        connection_key = self._clean(connection_key)
        keys = self._norm_keys(category_keys)
        code_list = [code for code in (self._clean(item) for item in (codes or [])) if code]
        if not connection_key or not keys or not code_list:
            return []
        return (
            self.db.query(Text2SQLCodeDictValue)
            .filter(
                Text2SQLCodeDictValue.connection_key == connection_key,
                Text2SQLCodeDictValue.category_key.in_(keys),
                Text2SQLCodeDictValue.code.in_(code_list),
            )
            .all()
        )
