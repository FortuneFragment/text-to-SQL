from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from repositories.text2sql_query_log_repo import Text2SQLQueryLogRepository
from schemas.text2sql import Text2SQLQueryLogItem


class Text2SQLLogService:
    """中文备注：封装服务层能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def _serialize_selected_tables(self, runtime_config: dict[str, Any]) -> str:
        """中文备注：处理selected tables相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return json.dumps(runtime_config.get("selected_tables", []), ensure_ascii=False)

    def create_success_log(
        self,
        *,
        db: Session,
        user_id: int,
        question: str,
        generated_sql: str | None,
        final_sql: str | None,
        runtime_config: dict[str, Any],
        row_count: int,
        duration_ms: int,
        repaired: bool,
    ) -> None:
        """中文备注：创建success log相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 核心处理：执行当前阶段的业务逻辑。
        Text2SQLQueryLogRepository(db).create(
            user_id=user_id,
            question=question,
            generated_sql=generated_sql,
            final_sql=final_sql,
            status="success",
            error_message=None,
            selected_tables=self._serialize_selected_tables(runtime_config),
            row_count=row_count,
            duration_ms=duration_ms,
            repaired=repaired,
        )

    def create_failed_log(
        self,
        *,
        db: Session,
        user_id: int,
        question: str,
        generated_sql: str | None,
        final_sql: str | None,
        runtime_config: dict[str, Any],
        error_message: str,
        duration_ms: int,
        repaired: bool,
    ) -> None:
        """中文备注：创建failed log相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 核心处理：执行当前阶段的业务逻辑。
        Text2SQLQueryLogRepository(db).create(
            user_id=user_id,
            question=question,
            generated_sql=generated_sql,
            final_sql=final_sql,
            status="failed",
            error_message=error_message,
            selected_tables=self._serialize_selected_tables(runtime_config),
            row_count=None,
            duration_ms=duration_ms,
            repaired=repaired,
        )

    def list_logs(self, db: Session, user_id: int, limit: int = 20) -> list[Text2SQLQueryLogItem]:
        """中文备注：列出logs相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `logs`。
        logs = Text2SQLQueryLogRepository(db).list_latest(user_id=user_id, limit=limit)
        # 2. 目标解析与合法性校验：解析输入范围并拦截非法数据。
        return [Text2SQLQueryLogItem.model_validate(item) for item in logs]

