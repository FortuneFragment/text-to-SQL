from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.text2sql_query_log import Text2SQLQueryLog

class Text2SQLQueryLogRepository:
    """负责查询日志的持久化与读取。"""
    def __init__(self, db: Session):
        """注入数据库会话。"""
        self.db = db

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
        row_count: int | None,
        duration_ms: int | None,
        repaired: bool,
    ) -> Text2SQLQueryLog:
        """写入一条查询日志。"""
        log = Text2SQLQueryLog(
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
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_latest(self, user_id: int, limit: int = 20) -> list[Text2SQLQueryLog]:
        """按时间倒序读取最近日志。"""
        return (
            self.db.query(Text2SQLQueryLog)
            .filter(Text2SQLQueryLog.user_id == user_id)
            .order_by(desc(Text2SQLQueryLog.created_at))
            .limit(limit)
            .all()
        )

