from services.text2sql.validator_service import Text2SQLValidatorService


def test_validate_sql_rejects_non_select():
    valid, message = Text2SQLValidatorService.validate_sql("DELETE FROM users")
    assert not valid
    assert "写操作" in message


def test_validate_sql_allows_join_with_whitelisted_tables():
    sql = "SELECT a.id, b.name FROM a JOIN b ON a.id=b.id LIMIT 10"
    valid, message = Text2SQLValidatorService.validate_sql(sql)
    assert valid
    assert message == ""


def test_validate_sql_checks_table_and_columns():
    sql = "SELECT id, name FROM student_scores LIMIT 10"
    valid, message = Text2SQLValidatorService.validate_sql(
        sql,
        allowed_tables=["student_scores"],
        table_columns_map={"student_scores": {"id", "name"}},
    )
    assert valid
    assert message == ""


def test_validate_sql_rejects_missing_column():
    sql = "SELECT id, not_exists FROM student_scores LIMIT 10"
    valid, message = Text2SQLValidatorService.validate_sql(
        sql,
        allowed_tables=["student_scores"],
        table_columns_map={"student_scores": {"id", "name"}},
    )
    assert not valid
    assert "字段不存在" in message


def test_validate_sql_rejects_too_many_tables():
    sql = "SELECT a.id FROM a JOIN b ON a.id=b.id JOIN c ON b.id=c.id LIMIT 10"
    valid, message = Text2SQLValidatorService.validate_sql(
        sql,
        allowed_tables=["a", "b", "c"],
        table_columns_map={"a": {"id"}, "b": {"id"}, "c": {"id"}},
        max_tables=2,
    )
    assert not valid
    assert "最多允许 2 张表" in message

