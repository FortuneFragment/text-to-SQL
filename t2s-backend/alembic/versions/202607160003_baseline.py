"""squashed baseline containing the complete current schema

Revision ID: 202607160003
Revises: None

Existing databases were upgraded to this revision before the migration history
was squashed. New databases can create the complete schema with one upgrade.
"""

from alembic import op
import sqlalchemy as sa


revision = "202607160003"
down_revision = None
branch_labels = None
depends_on = None


TABLE_OPTIONS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("collection_name", sa.String(length=128), nullable=False),
        sa.Column("usage_type", sa.String(length=32), nullable=False),
        sa.Column("default_chunk_size", sa.Integer(), nullable=False),
        sa.Column("default_chunk_overlap", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "usage_type IN ('table_route', 'document_qa', 'few_shot', "
            "'table_semantic_tree', 'data_dictionary')",
            name="ck_kb_usage_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_name"),
        sa.UniqueConstraint("id", "usage_type", name="uq_kb_id_usage"),
        **TABLE_OPTIONS,
    )
    op.create_index("idx_kb_usage", "knowledge_base", ["usage_type"], unique=False)
    op.create_index("ix_knowledge_base_name", "knowledge_base", ["name"], unique=True)

    op.create_table(
        "system_admin_whitelist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uni_code", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_system_admin_whitelist_uni_code",
        "system_admin_whitelist",
        ["uni_code"],
        unique=True,
    )

    op.create_table(
        "system_user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uni_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column("external_roles", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_system_user_uni_code", "system_user", ["uni_code"], unique=True)

    op.create_table(
        "text2sql_code_dict_binding",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("connection_key", sa.String(length=255), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("column_name", sa.String(length=128), nullable=False),
        sa.Column("category_key", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_key",
            "table_name",
            "column_name",
            name="uq_t2s_code_dict_binding_conn_table_col",
        ),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_text2sql_code_dict_binding_category_key",
        "text2sql_code_dict_binding",
        ["category_key"],
        unique=False,
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

    op.create_table(
        "text2sql_code_dict_value",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("connection_key", sa.String(length=255), nullable=False),
        sa.Column("category_key", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_key",
            "category_key",
            "code",
            name="uq_t2s_code_dict_value_conn_cat_code",
        ),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_text2sql_code_dict_value_category_key",
        "text2sql_code_dict_value",
        ["category_key"],
        unique=False,
    )
    op.create_index(
        "ix_text2sql_code_dict_value_connection_key",
        "text2sql_code_dict_value",
        ["connection_key"],
        unique=False,
    )

    op.create_table(
        "text2sql_connection",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("db_type", sa.String(length=32), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=1024), nullable=False),
        sa.Column("database", sa.String(length=255), nullable=False),
        sa.Column("db_schema", sa.String(length=128), nullable=True),
        sa.Column("charset", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "text2sql_model_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=False),
        sa.Column("api_key", sa.String(length=2048), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("vector_dim", sa.Integer(), nullable=True),
        sa.Column("batch_size", sa.Integer(), nullable=True),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False),
        sa.Column("ca_bundle", sa.Text(), nullable=True),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("retry_backoff_seconds", sa.Float(), nullable=False),
        sa.Column("trust_env", sa.Boolean(), nullable=False),
        sa.Column("extra_params", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_text2sql_model_config_is_active",
        "text2sql_model_config",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_text2sql_model_config_is_deleted",
        "text2sql_model_config",
        ["is_deleted"],
        unique=False,
    )
    op.create_index(
        "ix_text2sql_model_config_kind",
        "text2sql_model_config",
        ["kind"],
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
        sa.Column("relation_guard_used", sa.Boolean(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("repaired", sa.Boolean(), nullable=False),
        sa.Column("feedback_score", sa.Integer(), nullable=True),
        sa.Column("few_shot_status", sa.String(length=20), nullable=True),
        sa.Column("few_shot_reviewed_by", sa.Integer(), nullable=True),
        sa.Column("few_shot_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_text2sql_query_log_created_at",
        "text2sql_query_log",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_text2sql_query_log_few_shot_status",
        "text2sql_query_log",
        ["few_shot_status"],
        unique=False,
    )
    op.create_index(
        "ix_text2sql_query_log_user_id",
        "text2sql_query_log",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "text2sql_schema_annotation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("connection_key", sa.String(length=255), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("column_name", sa.String(length=128), nullable=False),
        sa.Column("table_comment", sa.Text(), nullable=True),
        sa.Column("column_comment", sa.Text(), nullable=True),
        sa.Column("aliases", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_key",
            "table_name",
            "column_name",
            name="uq_t2s_schema_annotation_conn_table_col",
        ),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_text2sql_schema_annotation_connection_key",
        "text2sql_schema_annotation",
        ["connection_key"],
        unique=False,
    )
    op.create_index(
        "ix_text2sql_schema_annotation_table_name",
        "text2sql_schema_annotation",
        ["table_name"],
        unique=False,
    )

    op.create_table(
        "text2sql_scoped_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("connection_key", sa.String(length=512), nullable=False),
        sa.Column("prompt_hint", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "connection_key",
            name="uq_t2s_scoped_config_user_conn",
        ),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_text2sql_scoped_config_connection_key",
        "text2sql_scoped_config",
        ["connection_key"],
        unique=False,
    )
    op.create_index(
        "ix_text2sql_scoped_config_user_id",
        "text2sql_scoped_config",
        ["user_id"],
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
        sa.Column("relation_type", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
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
        **TABLE_OPTIONS,
    )
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
    op.create_index(
        "ix_text2sql_table_relation_user_id",
        "text2sql_table_relation",
        ["user_id"],
        unique=False,
    )

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
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("table_task_meta_json", sa.Text(), nullable=True),
        sa.Column("custom_chunk_size", sa.Integer(), nullable=True),
        sa.Column("custom_chunk_overlap", sa.Integer(), nullable=True),
        sa.Column("usage_snapshot", sa.String(length=32), nullable=False),
        sa.Column("processor_type", sa.String(length=32), nullable=False),
        sa.Column("process_version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "usage_snapshot IN ('table_route', 'document_qa', 'few_shot', "
            "'table_semantic_tree', 'data_dictionary')",
            name="ck_file_usage_snapshot",
        ),
        sa.CheckConstraint(
            "processor_type IN ('generic_document', 'few_shot', "
            "'table_semantic', 'data_dictionary')",
            name="ck_file_processor_type",
        ),
        sa.CheckConstraint(
            "((usage_snapshot IN ('table_route', 'document_qa') "
            "AND processor_type = 'generic_document') "
            "OR (usage_snapshot = 'few_shot' AND processor_type = 'few_shot') "
            "OR (usage_snapshot = 'table_semantic_tree' "
            "AND processor_type = 'table_semantic') "
            "OR (usage_snapshot = 'data_dictionary' "
            "AND processor_type = 'data_dictionary'))",
            name="ck_file_usage_processor_pair",
        ),
        sa.CheckConstraint("process_version >= 1", name="ck_file_process_version_positive"),
        sa.ForeignKeyConstraint(
            ["kb_id", "usage_snapshot"],
            ["knowledge_base.id", "knowledge_base.usage_type"],
            name="fk_file_kb_usage",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "kb_id",
            "usage_snapshot",
            "processor_type",
            name="uq_file_context",
        ),
        sa.UniqueConstraint(
            "id",
            "kb_id",
            "usage_snapshot",
            name="uq_file_table_context",
        ),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "idx_file_kb_usage_active",
        "knowledge_file",
        ["kb_id", "usage_snapshot", "is_deleted"],
        unique=False,
    )
    op.create_index(
        "idx_file_processor_status",
        "knowledge_file",
        ["processor_type", "status", "is_deleted"],
        unique=False,
    )
    op.create_index(
        "idx_file_task_version",
        "knowledge_file",
        ["id", "process_version"],
        unique=False,
    )
    op.create_index("ix_knowledge_file_kb_id", "knowledge_file", ["kb_id"], unique=False)
    op.create_index("ix_knowledge_file_md5", "knowledge_file", ["md5"], unique=False)
    op.create_index("ix_knowledge_file_task_id", "knowledge_file", ["task_id"], unique=False)

    op.create_table(
        "document_chunk",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kb_id", sa.Integer(), nullable=False),
        sa.Column("usage_snapshot", sa.String(length=32), nullable=False),
        sa.Column("processor_type", sa.String(length=32), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "usage_snapshot IN ('table_route', 'document_qa', 'few_shot', "
            "'table_semantic_tree', 'data_dictionary')",
            name="ck_chunk_usage_snapshot",
        ),
        sa.CheckConstraint(
            "processor_type IN ('generic_document', 'few_shot', "
            "'table_semantic', 'data_dictionary')",
            name="ck_chunk_processor_type",
        ),
        sa.CheckConstraint(
            "((usage_snapshot IN ('table_route', 'document_qa') "
            "AND processor_type = 'generic_document') "
            "OR (usage_snapshot = 'few_shot' AND processor_type = 'few_shot') "
            "OR (usage_snapshot = 'table_semantic_tree' "
            "AND processor_type = 'table_semantic') "
            "OR (usage_snapshot = 'data_dictionary' "
            "AND processor_type = 'data_dictionary'))",
            name="ck_chunk_usage_processor_pair",
        ),
        sa.ForeignKeyConstraint(
            ["file_id", "kb_id", "usage_snapshot", "processor_type"],
            [
                "knowledge_file.id",
                "knowledge_file.kb_id",
                "knowledge_file.usage_snapshot",
                "knowledge_file.processor_type",
            ],
            name="fk_chunk_file_context",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "idx_chunk_kb_usage_file",
        "document_chunk",
        ["kb_id", "usage_snapshot", "file_id"],
        unique=False,
    )
    op.create_index("ix_document_chunk_file_id", "document_chunk", ["file_id"], unique=False)
    op.create_index("ix_document_chunk_kb_id", "document_chunk", ["kb_id"], unique=False)

    op.create_table(
        "table_semantic_artifact",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kb_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("usage_snapshot", sa.String(length=32), nullable=False),
        sa.Column("table_id", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=False),
        sa.Column("table_title", sa.String(length=255), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("candidate_fields_json", sa.Text(), nullable=False),
        sa.Column("tree_path_text_json", sa.Text(), nullable=False),
        sa.Column("tree_metric_names_json", sa.Text(), nullable=False),
        sa.Column("tree_object_name", sa.String(length=512), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "usage_snapshot = 'table_semantic_tree'",
            name="ck_table_artifact_usage",
        ),
        sa.ForeignKeyConstraint(
            ["file_id", "kb_id", "usage_snapshot"],
            ["knowledge_file.id", "knowledge_file.kb_id", "knowledge_file.usage_snapshot"],
            name="fk_table_artifact_file_context",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_table_semantic_artifact_file_id",
        "table_semantic_artifact",
        ["file_id"],
        unique=False,
    )
    op.create_index(
        "ix_table_semantic_artifact_kb_id",
        "table_semantic_artifact",
        ["kb_id"],
        unique=False,
    )
    op.create_index(
        "ix_table_semantic_artifact_table_id",
        "table_semantic_artifact",
        ["table_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("table_semantic_artifact")
    op.drop_table("document_chunk")
    op.drop_table("knowledge_file")
    op.drop_table("text2sql_table_relation")
    op.drop_table("text2sql_scoped_config")
    op.drop_table("text2sql_schema_annotation")
    op.drop_table("text2sql_query_log")
    op.drop_table("text2sql_model_config")
    op.drop_table("text2sql_connection")
    op.drop_table("text2sql_code_dict_value")
    op.drop_table("text2sql_code_dict_binding")
    op.drop_table("system_user")
    op.drop_table("system_admin_whitelist")
    op.drop_table("knowledge_base")
