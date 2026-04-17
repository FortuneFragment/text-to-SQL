from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Text2SQLFieldPermission(Base):
    """存储字段级查询开关配置。"""

    __tablename__ = "text2sql_field_permission"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "connection_key",
            "table_name",
            "column_name",
            name="uq_t2s_field_perm_user_conn_table_col",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    # utf8mb4 下联合索引容易超长，这里收敛长度以避免超过 MySQL 3072 字节限制。
    connection_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    column_name: Mapped[str] = mapped_column(String(64), nullable=False)
    query_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
