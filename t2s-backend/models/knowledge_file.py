from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class KnowledgeFile(Base):
    __tablename__ = "knowledge_file"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_base.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    md5: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    minio_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    minio_object_name: Mapped[str] = mapped_column(String(512), nullable=False)

    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    custom_chunk_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    custom_chunk_overlap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="files")
    chunks = relationship("DocumentChunk", back_populates="file")
