"""text2sql sqlserver schema and feedback

Revision ID: 202606230001
Revises: 202604280001
Create Date: 2026-06-23 00:01:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606230001"
down_revision: Union[str, Sequence[str], None] = "202604280001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name.lower() in {
        str(column.get("name") or "").lower()
        for column in inspector.get_columns(table_name)
    }


def upgrade() -> None:
    if not _has_column("text2sql_connection", "db_schema"):
        op.add_column("text2sql_connection", sa.Column("db_schema", sa.String(length=128), nullable=True))
    if not _has_column("text2sql_query_log", "feedback_score"):
        op.add_column("text2sql_query_log", sa.Column("feedback_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    if _has_column("text2sql_query_log", "feedback_score"):
        op.drop_column("text2sql_query_log", "feedback_score")
    if _has_column("text2sql_connection", "db_schema"):
        op.drop_column("text2sql_connection", "db_schema")
