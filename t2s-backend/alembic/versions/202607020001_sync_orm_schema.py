"""sync ORM schema drift

Revision ID: 202607020001
Revises: 202606300001
Create Date: 2026-07-02 00:01:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607020001"
down_revision: Union[str, Sequence[str], None] = "202606300001"
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


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return index_name.lower() in {
        str(index.get("name") or "").lower()
        for index in _inspector().get_indexes(table_name)
    }


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    _drop_column_if_exists("text2sql_config", "selected_tables")
    _drop_column_if_exists("text2sql_scoped_config", "selected_tables")

    if _has_index("text2sql_schema_annotation", "ix_text2sql_schema_annotation_category_key"):
        op.drop_index("ix_text2sql_schema_annotation_category_key", table_name="text2sql_schema_annotation")
    _drop_column_if_exists("text2sql_schema_annotation", "category_key")

    if _has_table("text2sql_value_dict"):
        if _has_table("text2sql_code_dict_value"):
            op.execute(
                sa.text(
                    """
                    INSERT IGNORE INTO text2sql_code_dict_value (
                        connection_key,
                        category_key,
                        code,
                        name
                    )
                    SELECT
                        connection_key,
                        category_key,
                        code,
                        name
                    FROM text2sql_value_dict
                    """
                )
            )
        op.drop_table("text2sql_value_dict")


def downgrade() -> None:
    # This revision removes schema drift that was never part of the previous
    # Alembic head, so downgrading should not recreate those drift artifacts.
    pass
