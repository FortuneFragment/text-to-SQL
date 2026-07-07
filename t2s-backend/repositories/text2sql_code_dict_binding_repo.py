from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from models.text2sql_code_dict_binding import Text2SQLCodeDictBinding


class Text2SQLCodeDictBindingRepository:
    """码值字段绑定持久化（按 connection_key 隔离）。

    绑定表只保存 table_name + column_name + category_key，全部绑定都参与编码/解码。
    表名/列名按大写归一存储，匹配由调用方统一大小写。
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _norm_ident(cls, value: Any) -> str:
        return cls._clean(value).upper()

    def _norm_tables(self, table_names: list[str] | None) -> list[str]:
        return [name for name in (self._norm_ident(item) for item in (table_names or [])) if name]

    def delete_by_connection(self, connection_key: str) -> int:
        connection_key = self._clean(connection_key)
        if not connection_key:
            return 0
        deleted = (
            self.db.query(Text2SQLCodeDictBinding)
            .filter(Text2SQLCodeDictBinding.connection_key == connection_key)
            .delete(synchronize_session=False)
        )
        return int(deleted or 0)

    def bulk_replace(self, connection_key: str, items: list[dict[str, Any]]) -> int:
        """整本替换某连接的字段绑定。"""
        connection_key = self._clean(connection_key)
        if not connection_key:
            return 0
        self.delete_by_connection(connection_key)
        return self.upsert_many(items)

    def upsert_many(self, items: list[dict[str, Any]], *, skip_reviewed: bool | None = None) -> int:
        """逐条 upsert。skip_reviewed 参数保留兼容旧调用，不再影响写入。"""
        _ = skip_reviewed
        count = 0
        for item in items:
            connection_key = self._clean(item.get("connection_key"))
            table_name = self._norm_ident(item.get("table_name"))
            column_name = self._norm_ident(item.get("column_name"))
            category_key = self._clean(item.get("category_key"))
            if not connection_key or not table_name or not column_name or not category_key:
                continue

            record = (
                self.db.query(Text2SQLCodeDictBinding)
                .filter(
                    Text2SQLCodeDictBinding.connection_key == connection_key,
                    Text2SQLCodeDictBinding.table_name == table_name,
                    Text2SQLCodeDictBinding.column_name == column_name,
                )
                .first()
            )
            if record is None:
                record = Text2SQLCodeDictBinding(
                    connection_key=connection_key,
                    table_name=table_name,
                    column_name=column_name,
                )
                self.db.add(record)

            record.category_key = category_key
            count += 1

        self.db.flush()
        return count

    def list_active_by_tables(
        self,
        connection_key: str,
        table_names: list[str],
    ) -> list[Text2SQLCodeDictBinding]:
        """编码/解码用：返回候选表的全部码值绑定。"""
        connection_key = self._clean(connection_key)
        tables = self._norm_tables(table_names)
        if not connection_key or not tables:
            return []
        return (
            self.db.query(Text2SQLCodeDictBinding)
            .filter(
                Text2SQLCodeDictBinding.connection_key == connection_key,
                Text2SQLCodeDictBinding.table_name.in_(tables),
            )
            .all()
        )

    def list_by_tables(
        self,
        connection_key: str,
        table_names: list[str],
    ) -> list[Text2SQLCodeDictBinding]:
        """管理用：返回候选表的全部绑定。"""
        return self.list_active_by_tables(connection_key, table_names)
