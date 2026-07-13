"""table semantic artifact

Revision ID: 202607070001
Revises: 202607030003
Create Date: 2026-07-07 00:01:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607070001"
down_revision: Union[str, Sequence[str], None] = "202607030003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return bool(sa.inspect(op.get_bind()).has_table(table_name))


def upgrade() -> None:
    if _has_table("table_semantic_artifact"):
        return

    op.create_table(
        "table_semantic_artifact",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kb_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("table_id", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=False),
        sa.Column("table_title", sa.String(length=255), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("candidate_fields_json", sa.Text(), nullable=False),
        sa.Column("tree_path_text_json", sa.Text(), nullable=False),
        sa.Column("tree_metric_names_json", sa.Text(), nullable=False),
        sa.Column("tree_object_name", sa.String(length=512), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("column_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["file_id"], ["knowledge_file.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_base.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("table_id"),
    )
    op.create_index("ix_table_semantic_artifact_file_id", "table_semantic_artifact", ["file_id"])
    op.create_index("ix_table_semantic_artifact_kb_id", "table_semantic_artifact", ["kb_id"])
    op.create_index("ix_table_semantic_artifact_table_id", "table_semantic_artifact", ["table_id"])


def downgrade() -> None:
    if not _has_table("table_semantic_artifact"):
        return
    op.drop_index("ix_table_semantic_artifact_table_id", table_name="table_semantic_artifact")
    op.drop_index("ix_table_semantic_artifact_kb_id", table_name="table_semantic_artifact")
    op.drop_index("ix_table_semantic_artifact_file_id", table_name="table_semantic_artifact")
    op.drop_table("table_semantic_artifact")
