from datetime import datetime
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from models.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunk"

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
            name="ck_chunk_usage_snapshot",
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
            name="ck_chunk_processor_type",
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
            name="ck_chunk_usage_processor_pair",
        ),
        ForeignKeyConstraint(
            [
                "file_id",
                "kb_id",
                "usage_snapshot",
                "processor_type",
            ],
            [
                "knowledge_file.id",
                "knowledge_file.kb_id",
                "knowledge_file.usage_snapshot",
                "knowledge_file.processor_type",
            ],
            name="fk_chunk_file_context",
            ondelete="CASCADE",
        ),
        Index(
            "idx_chunk_kb_usage_file",
            "kb_id",
            "usage_snapshot",
            "file_id",
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

    usage_snapshot: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    processor_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    file_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    file = relationship(
        "KnowledgeFile",
        back_populates="chunks",
    )
