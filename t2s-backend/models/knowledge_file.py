from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from models.base import Base


class KnowledgeFile(Base):
    __tablename__ = "knowledge_file"

    __table_args__ = (
        CheckConstraint(
            """
            usage_snapshot IN (
                'table_route',
                'document_qa',
                'few_shot',
                'table_semantic_tree',
                'data_dictionary'
            )
            """,
            name="ck_file_usage_snapshot",
        ),
        CheckConstraint(
            """
            processor_type IN (
                'generic_document',
                'few_shot',
                'table_semantic',
                'data_dictionary'
            )
            """,
            name="ck_file_processor_type",
        ),
        CheckConstraint(
            """
            (
                usage_snapshot IN (
                    'table_route',
                    'document_qa'
                )
                AND processor_type =
                    'generic_document'
            )
            OR (
                usage_snapshot = 'few_shot'
                AND processor_type = 'few_shot'
            )
            OR (
                usage_snapshot =
                    'table_semantic_tree'
                AND processor_type =
                    'table_semantic'
            )
            OR (
                usage_snapshot =
                    'data_dictionary'
                AND processor_type =
                    'data_dictionary'
            )
            """,
            name="ck_file_usage_processor_pair",
        ),
        CheckConstraint(
            "process_version >= 1",
            name="ck_file_process_version_positive",
        ),
        ForeignKeyConstraint(
            ["kb_id", "usage_snapshot"],
            [
                "knowledge_base.id",
                "knowledge_base.usage_type",
            ],
            name="fk_file_kb_usage",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "id",
            "kb_id",
            "usage_snapshot",
            "processor_type",
            name="uq_file_context",
        ),
        UniqueConstraint(
            "id",
            "kb_id",
            "usage_snapshot",
            name="uq_file_table_context",
        ),
        Index(
            "idx_file_kb_usage_active",
            "kb_id",
            "usage_snapshot",
            "is_deleted",
        ),
        Index(
            "idx_file_processor_status",
            "processor_type",
            "status",
            "is_deleted",
        ),
        Index(
            "idx_file_task_version",
            "id",
            "process_version",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    kb_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    md5: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    minio_bucket: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    minio_object_name: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    error_msg: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    table_task_meta_json: Mapped[
        Optional[str]
    ] = mapped_column(
        Text,
        nullable=True,
    )

    custom_chunk_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    custom_chunk_overlap: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    usage_snapshot: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    processor_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    process_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    knowledge_base = relationship(
        "KnowledgeBase",
        back_populates="files",
    )
    chunks = relationship(
        "DocumentChunk",
        back_populates="file",
    )
