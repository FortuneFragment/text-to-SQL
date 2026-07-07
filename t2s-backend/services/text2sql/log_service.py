from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from repositories.text2sql_query_log_repo import Text2SQLQueryLogRepository
from schemas.text2sql import Text2SQLQueryLogItem

_logger = logging.getLogger("text2sql.log")


class Text2SQLLogService:
    """Write query logs and record user feedback."""

    def _serialize_selected_tables(self, runtime_config: dict[str, Any]) -> str:
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
    ) -> int | None:
        log = Text2SQLQueryLogRepository(db).create(
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
        log_id = getattr(log, "id", None)
        return int(log_id) if log_id else None

    def update_feedback(
        self,
        db: Session,
        *,
        log_id: int,
        user_id: int,
        score: int,
        answer: str | None = None,
        question: str | None = None,
        sql: str | None = None,
        selected_tables: list[str] | None = None,
    ) -> bool:
        updated = Text2SQLQueryLogRepository(db).update_feedback(
            log_id=log_id,
            user_id=user_id,
            score=score,
        )
        if updated and int(score) >= 5:
            try:
                from services.text2sql.few_shot_service import few_shot_service

                few_shot_service.upsert_feedback_example(
                    db,
                    log_id=log_id,
                    user_id=user_id,
                    answer=answer,
                    question=question,
                    sql=sql,
                    selected_tables=selected_tables or [],
                )
            except Exception:  # noqa: BLE001
                _logger.exception("few-shot backflow failed for log_id=%s", log_id)
        return updated

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
        logs = Text2SQLQueryLogRepository(db).list_latest(user_id=user_id, limit=limit)
        return [Text2SQLQueryLogItem.model_validate(item) for item in logs]
