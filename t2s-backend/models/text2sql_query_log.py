from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base


class Text2SQLQueryLog(Base):
    """记录每次 Text2SQL 请求的 SQL 与执行结果。"""
    __tablename__ = "text2sql_query_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_sql: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    selected_tables: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relation_guard_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    repaired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
