from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from core.config import settings


class Text2SQLExecutorService:
    """中文备注：封装SQL 执行。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(
        self,
        engine_provider: Callable[[Session], Engine],
        ensure_limit: Callable[[str], str],
    ):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self._engine_provider`。
        self._engine_provider = engine_provider
        self._ensure_limit = ensure_limit

    def execute_sql(self, db: Session, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
        """中文备注：执行sql相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `engine`。
        engine = self._engine_provider(db)
        sql = self._ensure_limit(sql)

        # 2. 核心处理：执行当前阶段的业务逻辑。
        with engine.connect() as conn:
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

