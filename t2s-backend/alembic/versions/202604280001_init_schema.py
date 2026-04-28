"""initial schema

Revision ID: 202604280001
Revises:
Create Date: 2026-04-28 00:01:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202604280001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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

    op.create_table(
        "text2sql_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("selected_tables", sa.Text(), nullable=True),
        sa.Column("prompt_hint", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_text2sql_config_user_id", "text2sql_config", ["user_id"], unique=True)

    op.create_table(
        "text2sql_scoped_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("connection_key", sa.String(length=512), nullable=False),
        sa.Column("selected_tables", sa.Text(), nullable=True),
        sa.Column("prompt_hint", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "connection_key", name="uq_t2s_scoped_config_user_conn"),
    )
    op.create_index("ix_text2sql_scoped_config_user_id", "text2sql_scoped_config", ["user_id"], unique=False)
    op.create_index(
        "ix_text2sql_scoped_config_connection_key",
        "text2sql_scoped_config",
        ["connection_key"],
        unique=False,
    )

    op.create_table(
        "text2sql_query_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("generated_sql", sa.Text(), nullable=True),
        sa.Column("final_sql", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("selected_tables", sa.Text(), nullable=True),
        sa.Column("relation_guard_used", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("repaired", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_text2sql_query_log_user_id", "text2sql_query_log", ["user_id"], unique=False)

    op.create_table(
        "text2sql_connection",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("db_type", sa.String(length=32), server_default=sa.text("'mysql'"), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), server_default=sa.text("3306"), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=1024), nullable=False),
        sa.Column("database", sa.String(length=255), nullable=False),
        sa.Column("charset", sa.String(length=64), server_default=sa.text("'utf8mb4'"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

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

    op.create_table(
        "text2sql_table_relation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("connection_key", sa.String(length=255), nullable=False),
        sa.Column("source_table", sa.String(length=64), nullable=False),
        sa.Column("source_columns", sa.Text(), nullable=False),
        sa.Column("source_columns_hash", sa.String(length=64), nullable=False),
        sa.Column("target_table", sa.String(length=64), nullable=False),
        sa.Column("target_columns", sa.Text(), nullable=False),
        sa.Column("target_columns_hash", sa.String(length=64), nullable=False),
        sa.Column("relation_type", sa.String(length=16), server_default=sa.text("'N:1'"), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "connection_key",
            "source_table",
            "target_table",
            "source_columns_hash",
            "target_columns_hash",
            name="uq_t2s_relation_user_conn_pair_cols",
        ),
    )
    op.create_index("ix_text2sql_table_relation_user_id", "text2sql_table_relation", ["user_id"], unique=False)
    op.create_index(
        "ix_text2sql_table_relation_connection_key",
        "text2sql_table_relation",
        ["connection_key"],
        unique=False,
    )
    op.create_index(
        "ix_text2sql_table_relation_source_table",
        "text2sql_table_relation",
        ["source_table"],
        unique=False,
    )
    op.create_index(
        "ix_text2sql_table_relation_target_table",
        "text2sql_table_relation",
        ["target_table"],
        unique=False,
    )
    op.create_index("ix_text2sql_table_relation_is_active", "text2sql_table_relation", ["is_active"], unique=False)

    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("collection_name", sa.String(length=128), nullable=False),
        sa.Column("default_chunk_size", sa.Integer(), server_default=sa.text("800"), nullable=False),
        sa.Column("default_chunk_overlap", sa.Integer(), server_default=sa.text("120"), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_name"),
    )
    op.create_index("ix_knowledge_base_name", "knowledge_base", ["name"], unique=True)

    op.create_table(
        "knowledge_file",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kb_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("md5", sa.String(length=32), nullable=False),
        sa.Column("minio_bucket", sa.String(length=128), nullable=False),
        sa.Column("minio_object_name", sa.String(length=512), nullable=False),
        sa.Column("status", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("custom_chunk_size", sa.Integer(), nullable=True),
        sa.Column("custom_chunk_overlap", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_base.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_file_kb_id", "knowledge_file", ["kb_id"], unique=False)
    op.create_index("ix_knowledge_file_md5", "knowledge_file", ["md5"], unique=False)
    op.create_index("ix_knowledge_file_task_id", "knowledge_file", ["task_id"], unique=False)

    op.create_table(
        "document_chunk",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kb_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["knowledge_file.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunk_kb_id", "document_chunk", ["kb_id"], unique=False)
    op.create_index("ix_document_chunk_file_id", "document_chunk", ["file_id"], unique=False)


def downgrade() -> None:
    op.drop_table("document_chunk")
    op.drop_table("knowledge_file")
    op.drop_table("knowledge_base")
    op.drop_table("text2sql_table_relation")
    op.drop_table("text2sql_field_permission")
    op.drop_table("text2sql_connection")
    op.drop_table("text2sql_query_log")
    op.drop_table("text2sql_scoped_config")
    op.drop_table("text2sql_config")
    op.drop_table("user")
