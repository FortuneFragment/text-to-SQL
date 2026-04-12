from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Text2SQLScopedConfig(Base):
    __tablename__ = "text2sql_scoped_config"
    __table_args__ = (
        UniqueConstraint("user_id", "connection_key", name="uq_t2s_scoped_config_user_conn"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    connection_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)

    selected_tables: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
