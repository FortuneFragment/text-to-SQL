from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Text2SQLConfig(Base):
    """中文备注：封装配置管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    __tablename__ = "text2sql_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, unique=True, index=True)

    selected_tables: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
