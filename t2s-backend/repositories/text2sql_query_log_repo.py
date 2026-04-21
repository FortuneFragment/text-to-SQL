from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from models.text2sql_query_log import Text2SQLQueryLog


class Text2SQLQueryLogRepository:
    """Persistence and query helpers for Text2SQL query logs."""

    _relation_guard_column_checked: bool = False
    _relation_guard_column_available: bool = True

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _is_unknown_relation_guard_column_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "unknown column" in message and "relation_guard_used" in message

    @staticmethod
    def _as_datetime(value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.now()

    def _ensure_relation_guard_column(self) -> bool:
        """Best-effort schema compatibility: add relation_guard_used if missing."""
        cls = self.__class__
        if cls._relation_guard_column_checked:
            return cls._relation_guard_column_available

        cls._relation_guard_column_checked = True
        cls._relation_guard_column_available = True
        try:
            bind = self.db.get_bind()
            inspector = inspect(bind)
            columns = {
                str(col.get("name") or "").lower()
                for col in inspector.get_columns(Text2SQLQueryLog.__tablename__)
            }
            if "relation_guard_used" in columns:
                return True

            dialect_name = str(getattr(bind.dialect, "name", "") or "").lower()
            if dialect_name == "mysql":
                ddl = (
                    "ALTER TABLE text2sql_query_log "
                    "ADD COLUMN relation_guard_used TINYINT(1) NOT NULL DEFAULT 0"
                )
            else:
                ddl = (
                    "ALTER TABLE text2sql_query_log "
                    "ADD COLUMN relation_guard_used BOOLEAN NOT NULL DEFAULT 0"
                )
            self.db.execute(text(ddl))
            self.db.commit()
            return True
        except Exception:  # noqa: BLE001
            self.db.rollback()
            cls._relation_guard_column_available = False
            return False

    def _create_without_relation_guard(
        self,
        *,
        user_id: int,
        question: str,
        generated_sql: str | None,
        final_sql: str | None,
        status: str,
        error_message: str | None,
        selected_tables: str | None,
        row_count: int | None,
        duration_ms: int | None,
        repaired: bool,
    ) -> Text2SQLQueryLog:
        """Compatibility write for old schemas without relation_guard_used."""
        sql = text(
            """
            INSERT INTO text2sql_query_log
            (user_id, question, generated_sql, final_sql, status, error_message, selected_tables, row_count, duration_ms, repaired)
            VALUES
            (:user_id, :question, :generated_sql, :final_sql, :status, :error_message, :selected_tables, :row_count, :duration_ms, :repaired)
            """
        )
        self.db.execute(
            sql,
            {
                "user_id": int(user_id),
                "question": question,
                "generated_sql": generated_sql,
                "final_sql": final_sql,
                "status": status,
                "error_message": error_message,
                "selected_tables": selected_tables,
                "row_count": row_count,
                "duration_ms": duration_ms,
                "repaired": bool(repaired),
            },
        )
        self.db.commit()
        return Text2SQLQueryLog(
            user_id=int(user_id),
            question=question,
            generated_sql=generated_sql,
            final_sql=final_sql,
            status=status,
            error_message=error_message,
            selected_tables=selected_tables,
            relation_guard_used=False,
            row_count=row_count,
            duration_ms=duration_ms,
            repaired=bool(repaired),
            created_at=datetime.now(),
        )

    def create(
        self,
        *,
        user_id: int,
        question: str,
        generated_sql: str | None,
        final_sql: str | None,
        status: str,
        error_message: str | None,
        selected_tables: str | None,
        relation_guard_used: bool,
        row_count: int | None,
        duration_ms: int | None,
        repaired: bool,
    ) -> Text2SQLQueryLog:
        """Write one query log entry."""
        if not self._ensure_relation_guard_column():
            return self._create_without_relation_guard(
                user_id=user_id,
                question=question,
                generated_sql=generated_sql,
                final_sql=final_sql,
                status=status,
                error_message=error_message,
                selected_tables=selected_tables,
                row_count=row_count,
                duration_ms=duration_ms,
                repaired=repaired,
            )

        log = Text2SQLQueryLog(
            user_id=user_id,
            question=question,
            generated_sql=generated_sql,
            final_sql=final_sql,
            status=status,
            error_message=error_message,
            selected_tables=selected_tables,
            relation_guard_used=bool(relation_guard_used),
            row_count=row_count,
            duration_ms=duration_ms,
            repaired=repaired,
        )
        self.db.add(log)
        try:
            self.db.commit()
            self.db.refresh(log)
            return log
        except OperationalError as exc:
            if not self._is_unknown_relation_guard_column_error(exc):
                raise
            self.db.rollback()
            self.__class__._relation_guard_column_available = False
            return self._create_without_relation_guard(
                user_id=user_id,
                question=question,
                generated_sql=generated_sql,
                final_sql=final_sql,
                status=status,
                error_message=error_message,
                selected_tables=selected_tables,
                row_count=row_count,
                duration_ms=duration_ms,
                repaired=repaired,
            )

    def _list_latest_without_relation_guard(self, user_id: int, limit: int) -> list[Text2SQLQueryLog]:
        safe_limit = max(1, int(limit))
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    id,
                    user_id,
                    question,
                    generated_sql,
                    final_sql,
                    status,
                    error_message,
                    selected_tables,
                    row_count,
                    duration_ms,
                    repaired,
                    created_at
                FROM text2sql_query_log
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT {safe_limit}
                """
            ),
            {"user_id": int(user_id)},
        ).mappings().all()
        result: list[Text2SQLQueryLog] = []
        for item in rows:
            result.append(
                Text2SQLQueryLog(
                    id=int(item.get("id") or 0),
                    user_id=int(item.get("user_id") or 0),
                    question=str(item.get("question") or ""),
                    generated_sql=item.get("generated_sql"),
                    final_sql=item.get("final_sql"),
                    status=str(item.get("status") or ""),
                    error_message=item.get("error_message"),
                    selected_tables=item.get("selected_tables"),
                    relation_guard_used=False,
                    row_count=item.get("row_count"),
                    duration_ms=item.get("duration_ms"),
                    repaired=bool(item.get("repaired")),
                    created_at=self._as_datetime(item.get("created_at")),
                )
            )
        return result

    def list_latest(self, user_id: int, limit: int = 20) -> list[Text2SQLQueryLog]:
        """Read latest logs in descending created_at order."""
        if not self._ensure_relation_guard_column():
            return self._list_latest_without_relation_guard(user_id=user_id, limit=limit)
        try:
            return (
                self.db.query(Text2SQLQueryLog)
                .filter(Text2SQLQueryLog.user_id == user_id)
                .order_by(desc(Text2SQLQueryLog.created_at))
                .limit(limit)
                .all()
            )
        except OperationalError as exc:
            if not self._is_unknown_relation_guard_column_error(exc):
                raise
            self.db.rollback()
            self.__class__._relation_guard_column_available = False
            return self._list_latest_without_relation_guard(user_id=user_id, limit=limit)