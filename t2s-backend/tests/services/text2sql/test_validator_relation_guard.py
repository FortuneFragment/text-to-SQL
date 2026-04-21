from __future__ import annotations

from services.text2sql.validator_service import Text2SQLValidatorService


def test_validate_sql_allows_join_when_relation_whitelisted():
    sql = """
    SELECT s.id, c.name
    FROM t_student s
    JOIN t_class c ON s.class_id = c.id
    """
    ok, message = Text2SQLValidatorService.validate_sql(
        sql=sql,
        allowed_tables=["t_student", "t_class"],
        table_columns_map={
            "t_student": {"id", "class_id"},
            "t_class": {"id", "name"},
        },
        max_tables=2,
        relation_hints=[
            {
                "source_table": "t_student",
                "source_columns": ["class_id"],
                "target_table": "t_class",
                "target_columns": ["id"],
            }
        ],
    )
    assert ok is True
    assert message == ""


def test_validate_sql_rejects_unwhitelisted_join_condition():
    sql = """
    SELECT s.id, c.name
    FROM t_student s
    JOIN t_class c ON s.id = c.id
    """
    ok, message = Text2SQLValidatorService.validate_sql(
        sql=sql,
        allowed_tables=["t_student", "t_class"],
        table_columns_map={
            "t_student": {"id", "class_id"},
            "t_class": {"id", "name"},
        },
        max_tables=2,
        relation_hints=[
            {
                "source_table": "t_student",
                "source_columns": ["class_id"],
                "target_table": "t_class",
                "target_columns": ["id"],
            }
        ],
    )
    assert ok is False
    assert "白名单" in message


def test_validate_sql_rejects_non_equi_join_condition():
    sql = """
    SELECT s.id, c.name
    FROM t_student s
    JOIN t_class c ON s.class_id > c.id
    """
    ok, message = Text2SQLValidatorService.validate_sql(
        sql=sql,
        allowed_tables=["t_student", "t_class"],
        table_columns_map={
            "t_student": {"id", "class_id"},
            "t_class": {"id", "name"},
        },
        max_tables=2,
        relation_hints=[
            {
                "source_table": "t_student",
                "source_columns": ["class_id"],
                "target_table": "t_class",
                "target_columns": ["id"],
            }
        ],
    )
    assert ok is False
    assert "等值连接" in message


def test_validate_sql_allows_composite_key_join():
    sql = """
    SELECT u.id, o.order_no
    FROM t_user u
    JOIN t_order o ON u.tenant_id = o.tenant_id AND u.id = o.user_id
    """
    ok, message = Text2SQLValidatorService.validate_sql(
        sql=sql,
        allowed_tables=["t_user", "t_order"],
        table_columns_map={
            "t_user": {"id", "tenant_id"},
            "t_order": {"order_no", "tenant_id", "user_id"},
        },
        max_tables=2,
        relation_hints=[
            {
                "source_table": "t_user",
                "source_columns": ["tenant_id", "id"],
                "target_table": "t_order",
                "target_columns": ["tenant_id", "user_id"],
            }
        ],
    )
    assert ok is True
    assert message == ""


def test_validate_sql_rejects_multi_table_without_relation_hints():
    sql = """
    SELECT s.id, c.name
    FROM t_student s
    JOIN t_class c ON s.class_id = c.id
    """
    ok, message = Text2SQLValidatorService.validate_sql(
        sql=sql,
        allowed_tables=["t_student", "t_class"],
        table_columns_map={
            "t_student": {"id", "class_id"},
            "t_class": {"id", "name"},
        },
        max_tables=2,
        relation_hints=[],
    )
    assert ok is False
    assert "单表查询" in message or "未授权" in message
