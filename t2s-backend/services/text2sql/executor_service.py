"""Text2SQL SQL 执行服务。

在「目标业务库」上执行最终 SQL 并把结果转成前端可消费的结构。执行前会强制补 TOP，
并按配置开启只读事务、设置最大执行时间，避免误写数据或慢查询拖垮业务库；
同时把 Decimal/日期/bytes 等类型归一化为 JSON 友好的值。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from services.text2sql.sql_dialect import (
    DB_TYPE_SQLSERVER,
    normalize_db_type,
)


class Text2SQLExecutorService:
    """执行 SQL 并把结果转换成前端可消费的数据结构。"""

    _TEXT_BYTE_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936")

    def __init__(
        self,
        engine_provider: Callable[[Session], Engine],
        ensure_limit: Callable[[str], str],
        db_type_provider: Callable[[Session], str] | None = None,
    ):
        """注入数据库引擎提供器、SQL Server 限流器，以及当前连接库类型提供器。"""
        self._engine_provider = engine_provider
        self._ensure_limit = ensure_limit
        self._db_type_provider = db_type_provider

    def _resolve_db_type(self, db: Session) -> str:
        """解析当前连接的库类型；无提供器或解析失败时回退 SQL Server。"""
        if self._db_type_provider is None:
            return DB_TYPE_SQLSERVER
        try:
            return normalize_db_type(self._db_type_provider(db))
        except Exception:  # noqa: BLE001
            return DB_TYPE_SQLSERVER

    @staticmethod
    def _cjk_count(value: str) -> int:
        return sum(
            1
            for char in value
            if (
                "\u3400" <= char <= "\u9fff"
                or "\uf900" <= char <= "\ufaff"
            )
        )

    @staticmethod
    def _latin1_mojibake_signal_count(value: str) -> int:
        return sum(1 for char in value if "\u00a0" <= char <= "\u00ff" or char == "\ufffd")

    @classmethod
    def _is_better_repaired_text(cls, original: str, candidate: str) -> bool:
        if not candidate or candidate == original or "\ufffd" in candidate:
            return False
        original_signal = cls._latin1_mojibake_signal_count(original)
        if original_signal < 2:
            return False
        if cls._cjk_count(candidate) <= cls._cjk_count(original):
            return False
        return cls._latin1_mojibake_signal_count(candidate) < original_signal

    @classmethod
    def _repair_latin1_gbk_mojibake(cls, value: str) -> str:
        """修复 GBK/GB18030 字节被误按 Latin-1/CP1252 解码后的中文乱码。"""
        if not value or cls._latin1_mojibake_signal_count(value) < 2:
            return value

        for source_encoding in ("latin1", "cp1252"):
            try:
                raw = value.encode(source_encoding)
            except UnicodeEncodeError:
                continue
            for target_encoding in ("gb18030", "gbk", "cp936"):
                try:
                    candidate = raw.decode(target_encoding)
                except UnicodeDecodeError:
                    continue
                if cls._is_better_repaired_text(value, candidate):
                    return candidate
        return value

    @classmethod
    def _decode_bytes(cls, value: bytes) -> str:
        for encoding in cls._TEXT_BYTE_ENCODINGS:
            try:
                return cls._repair_latin1_gbk_mojibake(value.decode(encoding))
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="replace")

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if isinstance(value, bytes):
            return cls._decode_bytes(value)
        if isinstance(value, str):
            return cls._repair_latin1_gbk_mojibake(value)
        return value

    @classmethod
    def _normalize_result_columns(cls, raw_columns: Any) -> list[str]:
        columns: list[str] = []
        seen_counts: dict[str, int] = {}
        used_labels: set[str] = set()
        for index, raw_column in enumerate(raw_columns):
            base_label = cls._repair_latin1_gbk_mojibake(str(raw_column)).strip() or f"column_{index + 1}"
            count = seen_counts.get(base_label, 0) + 1
            seen_counts[base_label] = count
            label = base_label if count == 1 else f"{base_label}_{count}"
            while label in used_labels:
                count += 1
                seen_counts[base_label] = count
                label = f"{base_label}_{count}"
            used_labels.add(label)
            columns.append(label)
        return columns

    def _apply_session_guards(self, conn, db_type: str) -> None:
        """SQL Server 写操作由校验器拦截，建议业务库账号也只授予 SELECT 权限。"""
        try:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"))
        except Exception:  # noqa: BLE001
            pass

    def execute_sql(self, db: Session, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
        """执行 SQL 并返回列名与行数据。

        SQL 在流水线内部即为 SQL Server T-SQL，执行前只补默认 TOP 限流。
        """
        engine = self._engine_provider(db)
        db_type = self._resolve_db_type(db)
        sql = self._ensure_limit(sql)
        with engine.connect() as conn:
            self._apply_session_guards(conn, db_type)

            result = conn.execute(text(sql))
            columns = self._normalize_result_columns(result.keys())
            rows: list[dict[str, Any]] = []

            # 逐行转 dict，并把数据库特有类型归一化为 JSON 可序列化的值。
            for row in result.fetchall():
                row_dict: dict[str, Any] = {}
                for index, column in enumerate(columns):
                    row_dict[column] = self._normalize_value(row[index])
                rows.append(row_dict)

            return columns, rows

