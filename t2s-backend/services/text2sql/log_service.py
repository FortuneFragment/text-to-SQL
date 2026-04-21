from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from repositories.text2sql_query_log_repo import Text2SQLQueryLogRepository
from schemas.text2sql import Text2SQLQueryLogItem

class Text2SQLLogService:
    """封装查询日志写入与读取。"""
    def _serialize_selected_tables(self, runtime_config: dict[str, Any]) -> str:
        """把运行时表范围序列化为 JSON 字符串。"""
        return json.dumps(runtime_config.get("selected_tables", []), ensure_ascii=False)

    @staticmethod
    def _extract_relation_guard_used(runtime_config: dict[str, Any]) -> bool:
        return bool(runtime_config.get("relation_guard_used", False))

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
        """写入一次成功查询的日志。"""
        Text2SQLQueryLogRepository(db).create(
            user_id=user_id,
            question=question,
            generated_sql=generated_sql,
            final_sql=final_sql,
            status="success",
            error_message=None,
            selected_tables=self._serialize_selected_tables(runtime_config),
            relation_guard_used=self._extract_relation_guard_used(runtime_config),
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
        """写入一次失败查询的日志。"""
        Text2SQLQueryLogRepository(db).create(
            user_id=user_id,
            question=question,
            generated_sql=generated_sql,
            final_sql=final_sql,
            status="failed",
            error_message=error_message,
            selected_tables=self._serialize_selected_tables(runtime_config),
            relation_guard_used=self._extract_relation_guard_used(runtime_config),
            row_count=None,
            duration_ms=duration_ms,
            repaired=repaired,
        )

    def list_logs(self, db: Session, user_id: int, limit: int = 20) -> list[Text2SQLQueryLogItem]:
        """读取最近的查询日志列表。"""
        logs = Text2SQLQueryLogRepository(db).list_latest(user_id=user_id, limit=limit)
        return [Text2SQLQueryLogItem.model_validate(item) for item in logs]

