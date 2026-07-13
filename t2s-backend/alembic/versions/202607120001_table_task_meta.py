"""persist table semantic task metadata

Revision ID: 202607120001
Revises: fd19ed0b208e
Create Date: 2026-07-12
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607120001"
down_revision: Union[str, Sequence[str], None] = (
    "fd19ed0b208e"
)
branch_labels = None
depends_on = None


def _has_column(
    table_name: str,
    column_name: str,
) -> bool:
    inspector = sa.inspect(op.get_bind())

    return column_name.lower() in {
        str(column.get("name") or "").lower()
        for column in inspector.get_columns(
            table_name
        )
    }


def upgrade() -> None:
    if not _has_column(
        "knowledge_file",
        "table_task_meta_json",
    ):
        op.add_column(
            "knowledge_file",
            sa.Column(
                "table_task_meta_json",
                sa.Text(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    if _has_column(
        "knowledge_file",
        "table_task_meta_json",
    ):
        op.drop_column(
            "knowledge_file",
            "table_task_meta_json",
        )
