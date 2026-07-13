from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.knowledge_usage import KB_USAGE_TABLE_ROUTE
from models.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    __table_args__ = (
        CheckConstraint(
            """
            usage_type IN (
                'table_route',
                'document_qa',
                'few_shot',
                'table_semantic_tree',
                'data_dictionary'
            )
            """,
            name="ck_kb_usage_type",
        ),
        UniqueConstraint(
            "id",
            "usage_type",
            name="uq_kb_id_usage",
        ),
        Index(
            "idx_kb_usage",
            "usage_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    collection_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    usage: Mapped[str] = mapped_column("usage_type", String(32), nullable=False, default=KB_USAGE_TABLE_ROUTE)

    default_chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=800)
    default_chunk_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    files = relationship(
        "KnowledgeFile",
        back_populates="knowledge_base",
        passive_deletes=True,
    )
