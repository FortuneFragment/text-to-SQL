"""add knowledge base usage type

Revision ID: 202606290002
Revises: 202606290001
Create Date: 2026-06-29 00:02:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606290002"
down_revision: Union[str, Sequence[str], None] = "202606290001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return bool(inspector.has_table(table_name))


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name.lower() in {
        str(column.get("name") or "").lower()
        for column in inspector.get_columns(table_name)
    }


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name.lower() in {
        str(index.get("name") or "").lower()
        for index in inspector.get_indexes(table_name)
    }


def upgrade() -> None:
    table_name = "knowledge_base"
    index_name = "ix_knowledge_base_usage_type"
    if _has_table(table_name) and not _has_column(table_name, "usage_type"):
        op.add_column(
            table_name,
            sa.Column(
                "usage_type",
                sa.String(length=32),
                server_default=sa.text("'table_route'"),
                nullable=False,
            ),
        )
    if _has_column(table_name, "usage_type") and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, ["usage_type"], unique=False)


def downgrade() -> None:
    table_name = "knowledge_base"
    index_name = "ix_knowledge_base_usage_type"
    if _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)
    if _has_column(table_name, "usage_type"):
        op.drop_column(table_name, "usage_type")
