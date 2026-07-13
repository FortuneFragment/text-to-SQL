from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class TableSemanticArtifact(Base):
    __tablename__ = "table_semantic_artifact"

    __table_args__ = (
        CheckConstraint(
            "usage_snapshot = 'table_semantic_tree'",
            name="ck_table_artifact_usage",
        ),
        ForeignKeyConstraint(
            [
                "file_id",
                "kb_id",
                "usage_snapshot",
            ],
            [
                "knowledge_file.id",
                "knowledge_file.kb_id",
                "knowledge_file.usage_snapshot",
            ],
            name="fk_table_artifact_file_context",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    file_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )
    usage_snapshot: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    table_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_fields_json: Mapped[str] = mapped_column(Text, nullable=False)
    tree_path_text_json: Mapped[str] = mapped_column(Text, nullable=False)
    tree_metric_names_json: Mapped[str] = mapped_column(Text, nullable=False)
    tree_object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
