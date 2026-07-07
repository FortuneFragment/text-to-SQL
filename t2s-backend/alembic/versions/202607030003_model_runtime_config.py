"""model runtime config

Revision ID: 202607030003
Revises: 202607030002
Create Date: 2026-07-03 00:03:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607030003"
down_revision: Union[str, Sequence[str], None] = "202607030002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return bool(sa.inspect(op.get_bind()).has_table(table_name))


def upgrade() -> None:
    if _has_table("text2sql_model_config"):
        return

    op.create_table(
        "text2sql_model_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), server_default="openai_compatible", nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=False),
        sa.Column("api_key", sa.String(length=2048), server_default="", nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="120", nullable=False),
        sa.Column("vector_dim", sa.Integer(), nullable=True),
        sa.Column("batch_size", sa.Integer(), nullable=True),
        sa.Column("verify_ssl", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("ca_bundle", sa.Text(), nullable=True),
        sa.Column("max_retries", sa.Integer(), server_default="2", nullable=False),
        sa.Column("retry_backoff_seconds", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("trust_env", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("extra_params", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_text2sql_model_config_kind", "text2sql_model_config", ["kind"])
    op.create_index("ix_text2sql_model_config_is_active", "text2sql_model_config", ["is_active"])
    op.create_index("ix_text2sql_model_config_is_deleted", "text2sql_model_config", ["is_deleted"])


def downgrade() -> None:
    if not _has_table("text2sql_model_config"):
        return
    op.drop_index("ix_text2sql_model_config_is_deleted", table_name="text2sql_model_config")
    op.drop_index("ix_text2sql_model_config_is_active", table_name="text2sql_model_config")
    op.drop_index("ix_text2sql_model_config_kind", table_name="text2sql_model_config")
    op.drop_table("text2sql_model_config")
