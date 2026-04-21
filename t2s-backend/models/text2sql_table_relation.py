from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Text2SQLTableRelation(Base):
    """存储按连接隔离的表字段关联关系（支持复合键）。"""

    __tablename__ = "text2sql_table_relation"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "connection_key",
            "source_table",
            "target_table",
            "source_columns_hash",
            "target_columns_hash",
            name="uq_t2s_relation_user_conn_pair_cols",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    connection_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    source_table: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_columns: Mapped[str] = mapped_column(Text, nullable=False)
    source_columns_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    target_table: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_columns: Mapped[str] = mapped_column(Text, nullable=False)
    target_columns_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    relation_type: Mapped[str] = mapped_column(String(16), nullable=False, default="N:1")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
