from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Text2SQLSchemaAnnotation(Base):
    """System-side semantic overlay for business table and column metadata."""

    __tablename__ = "text2sql_schema_annotation"
    __table_args__ = (
        UniqueConstraint(
            "connection_key",
            "table_name",
            "column_name",
            name="uq_t2s_schema_annotation_conn_table_col",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    connection_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    column_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    table_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    column_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
