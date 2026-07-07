"""minimize text2sql code dictionary schema

Revision ID: 202607030001
Revises: 202607020002
Create Date: 2026-07-03 00:01:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607030001"
down_revision: Union[str, Sequence[str], None] = "202607020002"
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


def _drop_columns(table_name: str, column_names: list[str]) -> None:
    existing = [column for column in column_names if _has_column(table_name, column)]
    if not existing:
        return
    with op.batch_alter_table(table_name) as batch_op:
        for column in existing:
            batch_op.drop_column(column)


def upgrade() -> None:
    _drop_columns(
        "text2sql_code_dict_value",
        [
            "category_name_cn",
            "name_en",
            "parent_code",
            "source",
            "orders",
            "created_at",
            "updated_at",
        ],
    )
    _drop_columns(
        "text2sql_code_dict_binding",
        [
            "filter_expr",
            "confidence",
            "is_reviewed",
            "source",
            "created_at",
            "updated_at",
        ],
    )


def downgrade() -> None:
    if _has_table("text2sql_code_dict_value"):
        with op.batch_alter_table("text2sql_code_dict_value") as batch_op:
            if not _has_column("text2sql_code_dict_value", "category_name_cn"):
                batch_op.add_column(sa.Column("category_name_cn", sa.String(length=255), nullable=True))
            if not _has_column("text2sql_code_dict_value", "name_en"):
                batch_op.add_column(sa.Column("name_en", sa.Text(), nullable=True))
            if not _has_column("text2sql_code_dict_value", "parent_code"):
                batch_op.add_column(sa.Column("parent_code", sa.String(length=255), nullable=True))
            if not _has_column("text2sql_code_dict_value", "source"):
                batch_op.add_column(sa.Column("source", sa.String(length=64), server_default="import", nullable=False))
            if not _has_column("text2sql_code_dict_value", "orders"):
                batch_op.add_column(sa.Column("orders", sa.Integer(), server_default=sa.text("0"), nullable=False))
            if not _has_column("text2sql_code_dict_value", "created_at"):
                batch_op.add_column(sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
            if not _has_column("text2sql_code_dict_value", "updated_at"):
                batch_op.add_column(sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))

    if _has_table("text2sql_code_dict_binding"):
        with op.batch_alter_table("text2sql_code_dict_binding") as batch_op:
            if not _has_column("text2sql_code_dict_binding", "filter_expr"):
                batch_op.add_column(sa.Column("filter_expr", sa.Text(), nullable=True))
            if not _has_column("text2sql_code_dict_binding", "confidence"):
                batch_op.add_column(sa.Column("confidence", sa.String(length=16), server_default="medium", nullable=False))
            if not _has_column("text2sql_code_dict_binding", "is_reviewed"):
                batch_op.add_column(sa.Column("is_reviewed", sa.Boolean(), server_default=sa.text("0"), nullable=False))
            if not _has_column("text2sql_code_dict_binding", "source"):
                batch_op.add_column(sa.Column("source", sa.String(length=64), server_default="import", nullable=False))
            if not _has_column("text2sql_code_dict_binding", "created_at"):
                batch_op.add_column(sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
            if not _has_column("text2sql_code_dict_binding", "updated_at"):
                batch_op.add_column(sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
