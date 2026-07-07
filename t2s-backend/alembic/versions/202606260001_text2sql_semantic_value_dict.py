"""text2sql semantic annotations

Revision ID: 202606260001
Revises: 202606230001
Create Date: 2026-06-26 00:01:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606260001"
down_revision: Union[str, Sequence[str], None] = "202606230001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return bool(inspector.has_table(table_name))


def upgrade() -> None:
    if not _has_table("text2sql_schema_annotation"):
        op.create_table(
            "text2sql_schema_annotation",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("connection_key", sa.String(length=255), nullable=False),
            sa.Column("table_name", sa.String(length=128), nullable=False),
            sa.Column("column_name", sa.String(length=128), server_default="", nullable=False),
            sa.Column("table_comment", sa.Text(), nullable=True),
            sa.Column("column_comment", sa.Text(), nullable=True),
            sa.Column("aliases", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "connection_key",
                "table_name",
                "column_name",
                name="uq_t2s_schema_annotation_conn_table_col",
            ),
        )
        op.create_index(
            "ix_text2sql_schema_annotation_connection_key",
            "text2sql_schema_annotation",
            ["connection_key"],
            unique=False,
        )
        op.create_index(
            "ix_text2sql_schema_annotation_table_name",
            "text2sql_schema_annotation",
            ["table_name"],
            unique=False,
        )


def downgrade() -> None:
    if _has_table("text2sql_schema_annotation"):
        op.drop_table("text2sql_schema_annotation")
