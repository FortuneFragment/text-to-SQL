from services.text2sql.config_service import Text2SQLConfigService
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.facade_service import Text2SQLFacadeService
from services.text2sql.log_service import Text2SQLLogService
from services.text2sql.schema_service import Text2SQLSchemaService


def _build_facade_service() -> Text2SQLFacadeService:
    connection_service = Text2SQLConnectionService()
    schema_service = Text2SQLSchemaService(connection_service)
    config_service = Text2SQLConfigService(schema_service, connection_service)
    log_service = Text2SQLLogService()
    return Text2SQLFacadeService(
        connection_service=connection_service,
        schema_service=schema_service,
        config_service=config_service,
        log_service=log_service,
    )


def test_route_tables_widens_candidates_when_no_signal(monkeypatch):
    service = _build_facade_service()
    monkeypatch.setattr(
        service.schema_service,
        "get_live_table_columns_map",
        lambda db, tables: {
            "t_a": {"id"},
            "t_b": {"id"},
            "t_c": {"id"},
            "t_d": {"id"},
        },
    )

    route = service._route_tables(db=object(), question="帮我看有哪些体测项目", selected_tables=[])
    assert route["mode"] == "no_signal"
    assert route["candidates"] == ["t_a", "t_b", "t_c", "t_d"]


def test_evaluate_candidates_uses_all_allowed_tables(monkeypatch):
    service = _build_facade_service()
    candidate_tables = ["student", "major"]
    captured: dict = {}

    monkeypatch.setattr(
        service.generator_service,
        "generate_sql",
        lambda **kwargs: (
            "SELECT s.id, m.name FROM student s "
            "JOIN major m ON s.major_id = m.id LIMIT 10;"
        ),
    )
    monkeypatch.setattr(
        service.schema_service,
        "get_live_table_columns_map",
        lambda db, tables: {
            "student": {"id", "major_id"},
            "major": {"id", "name"},
        },
    )

    def _fake_validate(sql, allowed_tables=None, table_columns_map=None, max_tables=None):
        captured["allowed_tables"] = list(allowed_tables or [])
        captured["max_tables"] = max_tables
        return True, ""

    monkeypatch.setattr(service.validator_service, "validate_sql", _fake_validate)

    result = service._evaluate_candidates(
        db=object(),
        question="数学专业有哪些老师",
        candidate_tables=candidate_tables,
        prompt_hint="",
        repair_rounds=0,
    )

    assert result.is_valid is True
    assert captured["allowed_tables"] == candidate_tables
    assert int(captured["max_tables"]) >= 1
