"""text2sql code value dictionary (value + binding)

Revision ID: 202606300001
Revises: 202606290002
Create Date: 2026-06-30 00:01:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606300001"
down_revision: Union[str, Sequence[str], None] = "202606290002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return bool(inspector.has_table(table_name))


def upgrade() -> None:
    # 码值字典：category_key + code -> 中文释义。
    if not _has_table("text2sql_code_dict_value"):
        op.create_table(
            "text2sql_code_dict_value",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("connection_key", sa.String(length=255), nullable=False),
            sa.Column("category_key", sa.String(length=128), nullable=False),
            sa.Column("code", sa.String(length=255), server_default="", nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "connection_key",
                "category_key",
                "code",
                name="uq_t2s_code_dict_value_conn_cat_code",
            ),
        )
        op.create_index(
            "ix_text2sql_code_dict_value_connection_key",
            "text2sql_code_dict_value",
            ["connection_key"],
            unique=False,
        )
        op.create_index(
            "ix_text2sql_code_dict_value_category_key",
            "text2sql_code_dict_value",
            ["category_key"],
            unique=False,
        )

    # 字段绑定：业务表字段 -> 字典 category_key。
    if not _has_table("text2sql_code_dict_binding"):
        op.create_table(
            "text2sql_code_dict_binding",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("connection_key", sa.String(length=255), nullable=False),
            sa.Column("table_name", sa.String(length=128), nullable=False),
            sa.Column("column_name", sa.String(length=128), server_default="", nullable=False),
            sa.Column("category_key", sa.String(length=128), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "connection_key",
                "table_name",
                "column_name",
                name="uq_t2s_code_dict_binding_conn_table_col",
            ),
        )
        op.create_index(
            "ix_text2sql_code_dict_binding_connection_key",
            "text2sql_code_dict_binding",
            ["connection_key"],
            unique=False,
        )
        op.create_index(
            "ix_text2sql_code_dict_binding_table_name",
            "text2sql_code_dict_binding",
            ["table_name"],
            unique=False,
        )
        op.create_index(
            "ix_text2sql_code_dict_binding_category_key",
            "text2sql_code_dict_binding",
            ["category_key"],
            unique=False,
        )


def downgrade() -> None:
    if _has_table("text2sql_code_dict_binding"):
        op.drop_table("text2sql_code_dict_binding")
    if _has_table("text2sql_code_dict_value"):
        op.drop_table("text2sql_code_dict_value")
