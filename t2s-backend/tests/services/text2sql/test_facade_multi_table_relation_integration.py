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
        return {
            "t_student": {"id", "class_id", "name"},
            "t_class": {"id", "name"},
        }


class DummyConfigService:
    pass


class DummyLogService:
    def create_success_log(self, **kwargs):
        return None

    def create_failed_log(self, **kwargs):
        return None


class DummyRelationService:
    def __init__(self, relation_hints: list[dict]):
        self.relation_hints = relation_hints

    def get_active_relations_by_tables(self, db, table_names):
        normalized_tables = {str(item).strip().lower() for item in (table_names or []) if str(item).strip()}
        if not normalized_tables:
            return []
        filtered: list[dict] = []
        for hint in self.relation_hints:
            source_table = str(hint.get("source_table") or "").strip().lower()
            target_table = str(hint.get("target_table") or "").strip().lower()
            if source_table in normalized_tables and target_table in normalized_tables:
                filtered.append(dict(hint))
        return filtered

    @staticmethod
    def relation_hint_lines(relation_hints):
        return [str(item.get("summary") or "") for item in (relation_hints or []) if str(item.get("summary") or "").strip()]


def _build_facade(relation_hints: list[dict]) -> Text2SQLFacadeService:
    return Text2SQLFacadeService(
        connection_service=DummyConnectionService(),
        schema_service=DummySchemaService(),
        config_service=DummyConfigService(),
        relation_service=DummyRelationService(relation_hints),
        log_service=DummyLogService(),
    )


def test_run_pipeline_uses_relation_guard_for_multi_table(monkeypatch):
    facade = _build_facade(
        [
            {
                "source_table": "t_student",
                "source_columns": ["class_id"],
                "target_table": "t_class",
                "target_columns": ["id"],
                "summary": "t_student.class_id = t_class.id",
            }
        ]
    )
    monkeypatch.setattr(settings, "TEXT2SQL_MULTI_TABLE_ENABLED", True)
    monkeypatch.setattr(settings, "TEXT2SQL_MAX_JOIN_TABLES", 2)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_ENABLED", False)
    monkeypatch.setattr(settings, "TEXT2SQL_AUTO_REPAIR_ROUNDS", 0)

    monkeypatch.setattr(
        facade,
        "_route_tables",
        lambda db, question, selected_tables: {
            "mode": "multi",
            "candidates": ["t_student", "t_class"],
            "route_pool_tables": ["t_student", "t_class"],
            "scores": {"t_student": 1.0, "t_class": 0.9},
            "clarify_question": "",
        },
    )

    captured: dict[str, object] = {}

    def fake_generate_sql(*, db, question, runtime_config):
        captured["runtime_selected_tables"] = runtime_config.get("selected_tables") or []
        captured["runtime_relation_hints"] = runtime_config.get("relation_hints") or []
        return "SELECT s.name, c.name FROM t_student s JOIN t_class c ON s.class_id = c.id"

    def fake_validate_sql(sql, allowed_tables, table_columns_map, max_tables, relation_hints):
        captured["validate_max_tables"] = max_tables
        captured["validate_relation_hints"] = relation_hints
        return True, ""

    monkeypatch.setattr(facade.generator_service, "generate_sql", fake_generate_sql)
    monkeypatch.setattr(facade.validator_service, "validate_sql", fake_validate_sql)

    payload = facade._run_pipeline(
        db=object(),
        question="查询每个学生的班级名称",
        selected_tables=[],
        prompt_hint="",
        execute_sql=False,
    )

    assert payload["relation_guard_used"] is True
    assert payload["selected_tables"] == ["t_student", "t_class"]
    assert captured["runtime_selected_tables"] == ["t_student", "t_class"]
    assert len(captured["runtime_relation_hints"]) == 1
    assert int(captured["validate_max_tables"]) == 2
    assert payload["relation_hints"] == ["t_student.class_id = t_class.id"]


def test_run_pipeline_fallbacks_to_single_table_when_no_relation(monkeypatch):
    facade = _build_facade([])
    monkeypatch.setattr(settings, "TEXT2SQL_MULTI_TABLE_ENABLED", True)
    monkeypatch.setattr(settings, "TEXT2SQL_MAX_JOIN_TABLES", 2)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_ENABLED", False)
    monkeypatch.setattr(settings, "TEXT2SQL_AUTO_REPAIR_ROUNDS", 0)

    monkeypatch.setattr(
        facade,
        "_route_tables",
        lambda db, question, selected_tables: {
            "mode": "multi",
            "candidates": ["t_student", "t_class"],
            "route_pool_tables": ["t_student", "t_class"],
            "scores": {"t_student": 1.0, "t_class": 0.9},
            "clarify_question": "",
        },
    )

    captured: dict[str, object] = {}

    def fake_generate_sql(*, db, question, runtime_config):
        captured["runtime_selected_tables"] = runtime_config.get("selected_tables") or []
        captured["runtime_relation_hints"] = runtime_config.get("relation_hints") or []
        return "SELECT name FROM t_student"

    def fake_validate_sql(sql, allowed_tables, table_columns_map, max_tables, relation_hints):
        captured["validate_max_tables"] = max_tables
        captured["validate_relation_hints"] = relation_hints
        return True, ""

    monkeypatch.setattr(facade.generator_service, "generate_sql", fake_generate_sql)
    monkeypatch.setattr(facade.validator_service, "validate_sql", fake_validate_sql)

    payload = facade._run_pipeline(
        db=object(),
        question="查询学生名单",
        selected_tables=[],
        prompt_hint="",
        execute_sql=False,
    )

    assert payload["mode"] == "single_fallback"
    assert payload["relation_guard_used"] is False
    assert payload["selected_tables"] == ["t_student"]
    assert captured["runtime_selected_tables"] == ["t_student"]
    assert captured["runtime_relation_hints"] == []
    assert int(captured["validate_max_tables"]) == 1


def test_run_pipeline_expands_seed_table_by_relation_when_route_is_single(monkeypatch):
    facade = _build_facade(
        [
            {
                "source_table": "t_student",
                "source_columns": ["class_id"],
                "target_table": "t_class",
                "target_columns": ["id"],
                "summary": "t_student.class_id = t_class.id",
            }
        ]
    )
    monkeypatch.setattr(settings, "TEXT2SQL_MULTI_TABLE_ENABLED", True)
    monkeypatch.setattr(settings, "TEXT2SQL_MAX_JOIN_TABLES", 2)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_ENABLED", False)
    monkeypatch.setattr(settings, "TEXT2SQL_AUTO_REPAIR_ROUNDS", 0)

    monkeypatch.setattr(
        facade,
        "_route_tables",
        lambda db, question, selected_tables: {
            "mode": "single",
            "candidates": ["t_student"],
            "route_pool_tables": ["t_student"],
            "scores": {"t_student": 1.0, "t_class": 0.0},
            "clarify_question": "",
        },
    )

    captured: dict[str, object] = {}

    def fake_generate_sql(*, db, question, runtime_config):
        captured["runtime_selected_tables"] = runtime_config.get("selected_tables") or []
        captured["runtime_relation_hints"] = runtime_config.get("relation_hints") or []
        return "SELECT s.name, c.name FROM t_student s JOIN t_class c ON s.class_id = c.id"

    def fake_validate_sql(sql, allowed_tables, table_columns_map, max_tables, relation_hints):
        captured["validate_max_tables"] = max_tables
        captured["validate_relation_hints"] = relation_hints
        return True, ""

    monkeypatch.setattr(facade.generator_service, "generate_sql", fake_generate_sql)
    monkeypatch.setattr(facade.validator_service, "validate_sql", fake_validate_sql)

    payload = facade._run_pipeline(
        db=object(),
        question="查询每个学生所属班级名称",
        selected_tables=["t_student", "t_class"],
        prompt_hint="",
        execute_sql=False,
    )

    assert payload["mode"] == "multi_relation_fallback"
    assert payload["relation_guard_used"] is True
    assert payload["selected_tables"] == ["t_student", "t_class"]
    assert captured["runtime_selected_tables"] == ["t_student", "t_class"]
    assert len(captured["runtime_relation_hints"]) == 1
    assert int(captured["validate_max_tables"]) == 2


def test_run_pipeline_reselects_related_table_from_route_pool_when_top_n_has_no_relation(monkeypatch):
    facade = _build_facade(
        [
            {
                "source_table": "t_student",
                "source_columns": ["class_id"],
                "target_table": "t_class",
                "target_columns": ["id"],
                "summary": "t_student.class_id = t_class.id",
            }
        ]
    )
    monkeypatch.setattr(settings, "TEXT2SQL_MULTI_TABLE_ENABLED", True)
    monkeypatch.setattr(settings, "TEXT2SQL_MAX_JOIN_TABLES", 2)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_ENABLED", False)
    monkeypatch.setattr(settings, "TEXT2SQL_AUTO_REPAIR_ROUNDS", 0)

    monkeypatch.setattr(
        facade,
        "_route_tables",
        lambda db, question, selected_tables: {
            "mode": "multi",
            "candidates": ["t_student", "t_grade"],  # top-2 内无关系
            "route_pool_tables": ["t_student", "t_grade", "t_class"],  # pool 内存在可关联表
            "scores": {"t_student": 1.0, "t_grade": 0.95, "t_class": 0.7},
            "clarify_question": "",
        },
    )

    captured: dict[str, object] = {}

    def fake_generate_sql(*, db, question, runtime_config):
        captured["runtime_selected_tables"] = runtime_config.get("selected_tables") or []
        captured["runtime_relation_hints"] = runtime_config.get("relation_hints") or []
        return "SELECT s.name, c.name FROM t_student s JOIN t_class c ON s.class_id = c.id"

    def fake_validate_sql(sql, allowed_tables, table_columns_map, max_tables, relation_hints):
        captured["validate_max_tables"] = max_tables
        captured["validate_relation_hints"] = relation_hints
        return True, ""

    monkeypatch.setattr(facade.generator_service, "generate_sql", fake_generate_sql)
    monkeypatch.setattr(facade.validator_service, "validate_sql", fake_validate_sql)

    payload = facade._run_pipeline(
        db=object(),
        question="查询每个学生所在班级",
        selected_tables=[],
        prompt_hint="",
        execute_sql=False,
    )

    assert payload["relation_guard_used"] is True
    assert payload["selected_tables"] == ["t_student", "t_class"]
    assert captured["runtime_selected_tables"] == ["t_student", "t_class"]
    assert len(captured["runtime_relation_hints"]) == 1
    assert int(captured["validate_max_tables"]) == 2
