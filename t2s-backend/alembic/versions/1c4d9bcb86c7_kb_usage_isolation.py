"""kb_usage_isolation

Revision ID: 1c4d9bcb86c7
Revises: 202607070001
Create Date: 2026-07-10 17:58:55.502638
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c4d9bcb86c7'
down_revision: Union[str, Sequence[str], None] = '202607070001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 添加强制非空字段
    op.add_column(
        "knowledge_file",
        sa.Column(
            "usage_snapshot",
            sa.String(32),
            nullable=False,
        ),
    )

    op.add_column(
        "knowledge_file",
        sa.Column(
            "processor_type",
            sa.String(32),
            nullable=False,
        ),
    )

    op.add_column(
        "knowledge_file",
        sa.Column(
            "process_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    op.add_column(
        "document_chunk",
        sa.Column(
            "usage_snapshot",
            sa.String(32),
            nullable=False,
        ),
    )

    op.add_column(
        "document_chunk",
        sa.Column(
            "processor_type",
            sa.String(32),
            nullable=False,
        ),
    )

    op.add_column(
        "table_semantic_artifact",
        sa.Column(
            "usage_snapshot",
            sa.String(32),
            nullable=False,
        ),
    )

    # 2. 创建 CHECK 约束
    op.create_check_constraint(
        "ck_kb_usage_type",
        "knowledge_base",
        "usage_type IN ('table_route', 'document_qa', 'few_shot', 'table_semantic_tree', 'data_dictionary')",
    )

    op.create_check_constraint(
        "ck_file_usage_snapshot",
        "knowledge_file",
        "usage_snapshot IN ('table_route', 'document_qa', 'few_shot', 'table_semantic_tree', 'data_dictionary')",
    )

    op.create_check_constraint(
        "ck_file_processor_type",
        "knowledge_file",
        "processor_type IN ('generic_document', 'few_shot', 'table_semantic', 'data_dictionary')",
    )

    op.create_check_constraint(
        "ck_file_usage_processor_pair",
        "knowledge_file",
        """
        (usage_snapshot IN ('table_route', 'document_qa') AND processor_type = 'generic_document')
        OR (usage_snapshot = 'few_shot' AND processor_type = 'few_shot')
        OR (usage_snapshot = 'table_semantic_tree' AND processor_type = 'table_semantic')
        OR (usage_snapshot = 'data_dictionary' AND processor_type = 'data_dictionary')
        """,
    )

    op.create_check_constraint(
        "ck_file_process_version_positive",
        "knowledge_file",
        "process_version >= 1",
    )

    op.create_check_constraint(
        "ck_chunk_usage_snapshot",
        "document_chunk",
        "usage_snapshot IN ('table_route', 'document_qa', 'few_shot', 'table_semantic_tree', 'data_dictionary')",
    )

    op.create_check_constraint(
        "ck_chunk_processor_type",
        "document_chunk",
        "processor_type IN ('generic_document', 'few_shot', 'table_semantic', 'data_dictionary')",
    )

    op.create_check_constraint(
        "ck_chunk_usage_processor_pair",
        "document_chunk",
        """
        (usage_snapshot IN ('table_route', 'document_qa') AND processor_type = 'generic_document')
        OR (usage_snapshot = 'few_shot' AND processor_type = 'few_shot')
        OR (usage_snapshot = 'table_semantic_tree' AND processor_type = 'table_semantic')
        OR (usage_snapshot = 'data_dictionary' AND processor_type = 'data_dictionary')
        """,
    )

    op.create_check_constraint(
        "ck_table_artifact_usage",
        "table_semantic_artifact",
        "usage_snapshot = 'table_semantic_tree'",
    )

    # 3. 创建父表组合唯一键
    op.create_unique_constraint(
        "uq_kb_id_usage",
        "knowledge_base",
        ["id", "usage_type"],
    )

    op.create_unique_constraint(
        "uq_file_context",
        "knowledge_file",
        [
            "id",
            "kb_id",
            "usage_snapshot",
            "processor_type",
        ],
    )

    op.create_unique_constraint(
        "uq_file_table_context",
        "knowledge_file",
        [
            "id",
            "kb_id",
            "usage_snapshot",
        ],
    )

    # 4. 创建组合外键
    op.create_foreign_key(
        "fk_file_kb_usage",
        "knowledge_file",
        "knowledge_base",
        ["kb_id", "usage_snapshot"],
        ["id", "usage_type"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "fk_chunk_file_context",
        "document_chunk",
        "knowledge_file",
        [
            "file_id",
            "kb_id",
            "usage_snapshot",
            "processor_type",
        ],
        [
            "id",
            "kb_id",
            "usage_snapshot",
            "processor_type",
        ],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "fk_table_artifact_file_context",
        "table_semantic_artifact",
        "knowledge_file",
        [
            "file_id",
            "kb_id",
            "usage_snapshot",
        ],
        [
            "id",
            "kb_id",
            "usage_snapshot",
        ],
        ondelete="CASCADE",
    )

    # 5. 增加默认知识库生成列
    op.add_column(
        "knowledge_base",
        sa.Column(
            "active_default_usage",
            sa.String(32),
            sa.Computed(
                """
                CASE
                    WHEN is_default = 1
                     AND is_deleted = 0
                    THEN usage_type
                    ELSE NULL
                END
                """,
                persisted=True,
            ),
            nullable=True,
        ),
    )

    op.create_index(
        "uq_kb_active_default_usage",
        "knowledge_base",
        ["active_default_usage"],
        unique=True,
    )

    # 6. 创建查询索引
    op.create_index(
        "idx_kb_usage_active",
        "knowledge_base",
        ["usage_type", "is_deleted"],
    )
    op.create_index(
        "idx_kb_usage_default",
        "knowledge_base",
        ["usage_type", "is_default", "is_deleted"],
    )
    op.create_index(
        "idx_file_kb_usage_active",
        "knowledge_file",
        ["kb_id", "usage_snapshot", "is_deleted"],
    )
    op.create_index(
        "idx_file_processor_status",
        "knowledge_file",
        ["processor_type", "status", "is_deleted"],
    )
    op.create_index(
        "idx_file_task_version",
        "knowledge_file",
        ["id", "process_version"],
    )
    op.create_index(
        "idx_chunk_kb_usage_file",
        "document_chunk",
        ["kb_id", "usage_snapshot", "file_id"],
    )


def downgrade() -> None:
    # 1. 删除查询索引
    op.drop_index("idx_chunk_kb_usage_file", table_name="document_chunk")
    op.drop_index("idx_file_task_version", table_name="knowledge_file")
    op.drop_index("idx_file_processor_status", table_name="knowledge_file")
    op.drop_index("idx_file_kb_usage_active", table_name="knowledge_file")
    op.drop_index("idx_kb_usage_default", table_name="knowledge_base")
    op.drop_index("idx_kb_usage_active", table_name="knowledge_base")

    # 2. 删除默认知识库唯一索引
    op.drop_index("uq_kb_active_default_usage", table_name="knowledge_base")

    # 3. 删除生成列
    op.drop_column("knowledge_base", "active_default_usage")

    # 4. 删除组合外键
    op.drop_constraint("fk_table_artifact_file_context", "table_semantic_artifact", type_="foreignkey")
    op.drop_constraint("fk_chunk_file_context", "document_chunk", type_="foreignkey")
    op.drop_constraint("fk_file_kb_usage", "knowledge_file", type_="foreignkey")

    # 5. 删除组合唯一约束
    op.drop_constraint("uq_file_table_context", "knowledge_file", type_="unique")
    op.drop_constraint("uq_file_context", "knowledge_file", type_="unique")
    op.drop_constraint("uq_kb_id_usage", "knowledge_base", type_="unique")

    # 6. 删除 CHECK 约束
    op.drop_constraint("ck_table_artifact_usage", "table_semantic_artifact", type_="check")
    op.drop_constraint("ck_chunk_usage_processor_pair", "document_chunk", type_="check")
    op.drop_constraint("ck_chunk_processor_type", "document_chunk", type_="check")
    op.drop_constraint("ck_chunk_usage_snapshot", "document_chunk", type_="check")
    op.drop_constraint("ck_file_process_version_positive", "knowledge_file", type_="check")
    op.drop_constraint("ck_file_usage_processor_pair", "knowledge_file", type_="check")
    op.drop_constraint("ck_file_processor_type", "knowledge_file", type_="check")
    op.drop_constraint("ck_file_usage_snapshot", "knowledge_file", type_="check")
    op.drop_constraint("ck_kb_usage_type", "knowledge_base", type_="check")

    # 7. 删除新增字段
    op.drop_column("table_semantic_artifact", "usage_snapshot")
    op.drop_column("document_chunk", "processor_type")
    op.drop_column("document_chunk", "usage_snapshot")
    op.drop_column("knowledge_file", "process_version")
    op.drop_column("knowledge_file", "processor_type")
    op.drop_column("knowledge_file", "usage_snapshot")
