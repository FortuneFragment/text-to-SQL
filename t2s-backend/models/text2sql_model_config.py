from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Text2SQLModelConfig(Base):
    __tablename__ = "text2sql_model_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="openai_compatible")
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    api_key: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)

    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    vector_dim: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    batch_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ca_bundle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    retry_backoff_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    trust_env: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    extra_params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
