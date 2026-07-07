"""remove user table and schema annotation flags

Revision ID: 202607030002
Revises: 202607030001
Create Date: 2026-07-03 00:02:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607030002"
down_revision: Union[str, Sequence[str], None] = "202607030001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return bool(_inspector().has_table(table_name))


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name.lower() in {
        str(column.get("name") or "").lower()
        for column in _inspector().get_columns(table_name)
    }


def upgrade() -> None:
    if _has_table("text2sql_schema_annotation"):
        with op.batch_alter_table("text2sql_schema_annotation") as batch_op:
            if _has_column("text2sql_schema_annotation", "source"):
                batch_op.drop_column("source")
            if _has_column("text2sql_schema_annotation", "is_reviewed"):
                batch_op.drop_column("is_reviewed")

    if _has_table("user"):
        op.drop_table("user")


def downgrade() -> None:
    if _has_table("text2sql_schema_annotation"):
        with op.batch_alter_table("text2sql_schema_annotation") as batch_op:
            if not _has_column("text2sql_schema_annotation", "source"):
                batch_op.add_column(sa.Column("source", sa.String(length=32), server_default="import", nullable=False))
            if not _has_column("text2sql_schema_annotation", "is_reviewed"):
                batch_op.add_column(sa.Column("is_reviewed", sa.Boolean(), server_default=sa.text("0"), nullable=False))

    if not _has_table("user"):
        op.create_table(
            "user",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("is_admin", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_user_username", "user", ["username"], unique=True)
        op.create_index("ix_user_email", "user", ["email"], unique=True)
