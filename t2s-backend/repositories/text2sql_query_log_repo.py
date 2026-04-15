from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.text2sql_query_log import Text2SQLQueryLog


class Text2SQLQueryLogRepository:
    """中文备注：封装数据存储访问。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(self, db: Session):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self.db`。
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
        """中文备注：创建相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `log`。
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
        # 2. 返回结果：输出当前函数最终结果。
        return log

    def list_latest(self, user_id: int, limit: int = 20) -> list[Text2SQLQueryLog]:
        """中文备注：列出latest相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return (
            self.db.query(Text2SQLQueryLog)
            .filter(Text2SQLQueryLog.user_id == user_id)
            .order_by(desc(Text2SQLQueryLog.created_at))
            .limit(limit)
            .all()
        )

