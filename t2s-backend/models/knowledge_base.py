from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    collection_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    default_chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=800)
    default_chunk_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    files = relationship("KnowledgeFile", back_populates="knowledge_base")
