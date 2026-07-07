"""remove table and field switch configuration

Revision ID: 202606260002
Revises: 202606260001
Create Date: 2026-06-26 00:02:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606260002"
down_revision: Union[str, Sequence[str], None] = "202606260001"
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


def upgrade() -> None:
    if _has_table("text2sql_field_permission"):
        op.drop_table("text2sql_field_permission")

    if _has_column("text2sql_config", "selected_tables"):
        op.drop_column("text2sql_config", "selected_tables")
    if _has_column("text2sql_scoped_config", "selected_tables"):
        op.drop_column("text2sql_scoped_config", "selected_tables")


def downgrade() -> None:
    if _has_table("text2sql_config") and not _has_column("text2sql_config", "selected_tables"):
        op.add_column("text2sql_config", sa.Column("selected_tables", sa.Text(), nullable=True))
    if _has_table("text2sql_scoped_config") and not _has_column("text2sql_scoped_config", "selected_tables"):
        op.add_column("text2sql_scoped_config", sa.Column("selected_tables", sa.Text(), nullable=True))

    if not _has_table("text2sql_field_permission"):
        op.create_table(
            "text2sql_field_permission",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("connection_key", sa.String(length=255), nullable=False),
            sa.Column("table_name", sa.String(length=64), nullable=False),
            sa.Column("column_name", sa.String(length=64), nullable=False),
            sa.Column("query_enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "connection_key",
                "table_name",
                "column_name",
                name="uq_t2s_field_perm_user_conn_table_col",
            ),
        )
        op.create_index("ix_text2sql_field_permission_user_id", "text2sql_field_permission", ["user_id"], unique=False)
        op.create_index(
            "ix_text2sql_field_permission_connection_key",
            "text2sql_field_permission",
            ["connection_key"],
            unique=False,
        )
        op.create_index(
            "ix_text2sql_field_permission_table_name",
            "text2sql_field_permission",
            ["table_name"],
            unique=False,
        )
