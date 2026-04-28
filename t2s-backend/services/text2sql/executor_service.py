from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from core.config import settings

class Text2SQLExecutorService:
    """执行 SQL 并把结果转换成前端可消费的数据结构。"""
    def __init__(
        self,
        engine_provider: Callable[[Session], Engine],
        ensure_limit: Callable[[str], str],
    ):
        """注入数据库引擎提供器和 SQL 限流器。"""
        self._engine_provider = engine_provider
        self._ensure_limit = ensure_limit

    def execute_sql(self, db: Session, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
        """执行 SQL 并返回列名与行数据。"""
        engine = self._engine_provider(db)
        sql = self._ensure_limit(sql)
        with engine.connect() as conn:
            try:
                transaction_mode = "READ ONLY" if settings.TEXT2SQL_READONLY else "READ WRITE"
                conn.execute(text(f"SET SESSION TRANSACTION {transaction_mode}"))
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("无法设置会话事务模式，请检查数据库事务配置") from exc

            timeout_ms = settings.TEXT2SQL_EXEC_TIMEOUT_SECONDS * 1000
            try:
                conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME={timeout_ms}"))
            except Exception:  # noqa: BLE001
                pass

            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows: list[dict[str, Any]] = []

            for row in result.fetchall():
                row_dict: dict[str, Any] = {}
                for index, column in enumerate(columns):
                    value = row[index]

                    if isinstance(value, Decimal):
                        value = float(value)
                    elif hasattr(value, "isoformat"):
                        value = value.isoformat()
                    elif isinstance(value, bytes):
                        value = value.decode("utf-8", errors="replace")

                    row_dict[column] = value
                rows.append(row_dict)

            return columns, rows

