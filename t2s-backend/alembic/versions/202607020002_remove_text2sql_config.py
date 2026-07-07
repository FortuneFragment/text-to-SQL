"""remove legacy text2sql config table

Revision ID: 202607020002
Revises: 202607020001
Create Date: 2026-07-02 00:02:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607020002"
down_revision: Union[str, Sequence[str], None] = "202607020001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UNCONFIGURED_CONNECTION_KEY = "unconfigured"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return bool(_inspector().has_table(table_name))


def _normalize_key_part(value) -> str:
    return str(value or "").strip().lower()


def _connection_keys() -> list[str]:
    keys = [_UNCONFIGURED_CONNECTION_KEY]
    if not _has_table("text2sql_connection"):
        return keys

    bind = op.get_bind()
    connection_table = sa.table(
        "text2sql_connection",
        sa.column("db_type"),
        sa.column("host"),
        sa.column("port"),
        sa.column("database"),
        sa.column("db_schema"),
        sa.column("username"),
    )
    rows = bind.execute(
        sa.select(
            connection_table.c.db_type,
            connection_table.c.host,
            connection_table.c.port,
            connection_table.c.database,
            connection_table.c.db_schema,
            connection_table.c.username,
        )
    ).mappings()
    for row in rows:
        if not row.get("host") or not row.get("database") or not row.get("username"):
            continue
        key = "|".join(
            [
                _normalize_key_part(row.get("db_type") or "sqlserver"),
                _normalize_key_part(row.get("host")),
                str(int(row.get("port") or 1433)),
                _normalize_key_part(row.get("database")),
                _normalize_key_part(row.get("db_schema")),
                _normalize_key_part(row.get("username")),
            ]
        )
        if key not in keys:
            keys.append(key)
    return keys


def _copy_legacy_prompt_hints() -> None:
    if not _has_table("text2sql_config") or not _has_table("text2sql_scoped_config"):
        return

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT user_id, prompt_hint
            FROM text2sql_config
            WHERE is_deleted = 0
              AND prompt_hint IS NOT NULL
              AND prompt_hint <> ''
            """
        )
    ).mappings()
    connection_keys = _connection_keys()
    for row in rows:
        for connection_key in connection_keys:
            params = {
                "user_id": int(row["user_id"] or 1),
                "connection_key": connection_key,
                "prompt_hint": row["prompt_hint"],
            }
            exists = bind.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM text2sql_scoped_config
                    WHERE user_id = :user_id
                      AND connection_key = :connection_key
                    LIMIT 1
                    """
                ),
                params,
            ).first()
            if exists:
                continue
            bind.execute(
                sa.text(
                    """
                    INSERT INTO text2sql_scoped_config (
                        user_id,
                        connection_key,
                        prompt_hint,
                        is_deleted,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :user_id,
                        :connection_key,
                        :prompt_hint,
                        0,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                params,
            )


def upgrade() -> None:
    _copy_legacy_prompt_hints()
    if _has_table("text2sql_config"):
        op.drop_table("text2sql_config")


def downgrade() -> None:
    if _has_table("text2sql_config"):
        return
    op.create_table(
        "text2sql_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("prompt_hint", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_text2sql_config_user_id", "text2sql_config", ["user_id"], unique=True)
