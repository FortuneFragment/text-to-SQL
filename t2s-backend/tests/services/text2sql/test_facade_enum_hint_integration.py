from __future__ import annotations

from core.config import settings
from services.text2sql.facade_service import Text2SQLFacadeService


class DummyConnectionService:
    def get_engine(self, db):
        return None


class DummySchemaService:
    def list_table_options(self, db):
        return []

    def validate_selected_tables(self, db, table_names):
        return table_names or [], []

    def get_live_table_columns_map(self, db, table_names=None, queryable_columns_map=None):
        return {"t_student": {"status"}}


class DummyConfigService:
    pass


class DummyFieldPermissionService:
    def get_queryable_columns_map(self, db, table_names=None):
        return {"t_student": {"status"}}

    def get_queryable_table_names(self, db, table_names=None):
        return ["t_student"]

    def build_query_field_comment_bindings(self, **kwargs):
        return []


class DummyLogService:
    def create_success_log(self, **kwargs):
        return None

    def create_failed_log(self, **kwargs):
        return None


class DummyEnumHintService:
    def __init__(self, enhanced_hint: str):
        self.enhanced_hint = enhanced_hint

    def build_prompt_hint(self, **kwargs):
        return self.enhanced_hint


class GuardEnumHintService:
    def build_prompt_hint(self, **kwargs):
        raise AssertionError("enum hint should not be called when disabled")


class DummyRelationService:
    def get_active_relations_by_tables(self, db, table_names):
        return []

    @staticmethod
    def relation_hint_lines(relation_hints):
        return []


def _build_facade() -> Text2SQLFacadeService:
    return Text2SQLFacadeService(
        connection_service=DummyConnectionService(),
        schema_service=DummySchemaService(),
        config_service=DummyConfigService(),
        field_permission_service=DummyFieldPermissionService(),
        relation_service=DummyRelationService(),
        log_service=DummyLogService(),
    )


def test_run_pipeline_passes_enhanced_prompt_to_generate_and_repair(monkeypatch):
    facade = _build_facade()
    enhanced_hint = '原始提示\\n\\nenum_hints_json:\\n{"enum_hints":{"t_student":{"status":["在读"]}}}'
    facade.enum_hint_service = DummyEnumHintService(enhanced_hint)

    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_ENABLED", True)
    monkeypatch.setattr(settings, "TEXT2SQL_AUTO_REPAIR_ROUNDS", 1)

    monkeypatch.setattr(
        facade,
        "_route_tables",
        lambda db, question, selected_tables: {
            "mode": "single",
            "candidates": ["t_student"],
            "scores": {"t_student": 1.0},
            "clarify_question": "",
        },
    )

    captured: dict[str, str] = {}

    def fake_generate_sql(*, db, question, runtime_config):
        captured["generate_prompt"] = runtime_config.get("prompt_hint") or ""
        return "SELECT status FROM t_student"

    repair_calls = {"count": 0}

    def fake_validate_sql(sql, allowed_tables, table_columns_map, max_tables, relation_hints):
        repair_calls["count"] += 1
        if repair_calls["count"] == 1:
            return False, "mock validation error"
        return True, ""

    def fake_repair_sql(*, db, question, failed_sql, error_message, runtime_config):
        captured["repair_prompt"] = runtime_config.get("prompt_hint") or ""
        return failed_sql

    monkeypatch.setattr(facade.generator_service, "generate_sql", fake_generate_sql)
    monkeypatch.setattr(facade.validator_service, "validate_sql", fake_validate_sql)
    monkeypatch.setattr(facade.repair_service, "repair_sql", fake_repair_sql)

    payload = facade._run_pipeline(
        db=object(),
        question="查询学生状态",
        selected_tables=[],
        prompt_hint="原始提示",
        execute_sql=False,
    )

    assert "enum_hints_json" in captured["generate_prompt"]
    assert captured["repair_prompt"] == captured["generate_prompt"]
    assert payload["repaired"] is True


def test_run_pipeline_keeps_original_prompt_when_enum_hint_disabled(monkeypatch):
    facade = _build_facade()
    facade.enum_hint_service = GuardEnumHintService()

    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_ENABLED", False)
    monkeypatch.setattr(settings, "TEXT2SQL_AUTO_REPAIR_ROUNDS", 0)

    monkeypatch.setattr(
        facade,
        "_route_tables",
        lambda db, question, selected_tables: {
            "mode": "single",
            "candidates": ["t_student"],
            "scores": {"t_student": 1.0},
            "clarify_question": "",
        },
    )

    captured: dict[str, str] = {}

    def fake_generate_sql(*, db, question, runtime_config):
        captured["generate_prompt"] = runtime_config.get("prompt_hint") or ""
        return "SELECT status FROM t_student"

    monkeypatch.setattr(facade.generator_service, "generate_sql", fake_generate_sql)
    monkeypatch.setattr(
        facade.validator_service,
        "validate_sql",
        lambda sql, allowed_tables, table_columns_map, max_tables, relation_hints: (True, ""),
    )

    facade._run_pipeline(
        db=object(),
        question="查询学生状态",
        selected_tables=[],
        prompt_hint="保留原始提示",
        execute_sql=False,
    )

    assert captured["generate_prompt"] == "保留原始提示"
