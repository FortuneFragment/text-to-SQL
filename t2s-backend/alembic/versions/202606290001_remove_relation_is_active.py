"""remove relation is_active flag

Revision ID: 202606290001
Revises: 202606260002
Create Date: 2026-06-29 00:01:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606290001"
down_revision: Union[str, Sequence[str], None] = "202606260002"
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
    table_name = "text2sql_table_relation"
    index_name = "ix_text2sql_table_relation_is_active"
    if _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)
    if _has_column(table_name, "is_active"):
        op.drop_column(table_name, "is_active")
    if _has_column("text2sql_connection", "db_type"):
        op.alter_column(
            "text2sql_connection",
            "db_type",
            existing_type=sa.String(length=32),
            server_default=sa.text("'sqlserver'"),
            existing_nullable=False,
        )


def downgrade() -> None:
    table_name = "text2sql_table_relation"
    index_name = "ix_text2sql_table_relation_is_active"
    if _has_table(table_name) and not _has_column(table_name, "is_active"):
        op.add_column(
            table_name,
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        )
    if _has_column(table_name, "is_active") and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, ["is_active"], unique=False)
    if _has_column("text2sql_connection", "db_type"):
        op.alter_column(
            "text2sql_connection",
            "db_type",
            existing_type=sa.String(length=32),
            server_default=sa.text("'mysql'"),
            existing_nullable=False,
        )
