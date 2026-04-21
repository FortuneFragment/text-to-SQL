from __future__ import annotations

import pytest

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
        return {}


class DummyConfigService:
    pass


class DummyFieldPermissionService:
    def get_queryable_columns_map(self, db, table_names=None):
        return {}

    def get_queryable_table_names(self, db, table_names=None):
        return []

    def build_query_field_comment_bindings(self, **kwargs):
        return []


class DummyRelationService:
    def get_active_relations_by_tables(self, db, table_names):
        return []

    @staticmethod
    def relation_hint_lines(relation_hints):
        return []


class FailingSuccessLogService:
    def create_success_log(self, **kwargs):
        raise RuntimeError("success log failed")

    def create_failed_log(self, **kwargs):
        return None


class FailingFailedLogService:
    def create_success_log(self, **kwargs):
        return None

    def create_failed_log(self, **kwargs):
        raise RuntimeError("failed log failed")


class DummyDbSession:
    def __init__(self):
        self.rollback_calls = 0

    def rollback(self):
        self.rollback_calls += 1


def _build_facade(log_service) -> Text2SQLFacadeService:
    return Text2SQLFacadeService(
        connection_service=DummyConnectionService(),
        schema_service=DummySchemaService(),
        config_service=DummyConfigService(),
        field_permission_service=DummyFieldPermissionService(),
        relation_service=DummyRelationService(),
        log_service=log_service,
    )


def test_query_ignores_success_log_write_error(monkeypatch):
    facade = _build_facade(FailingSuccessLogService())
    db = DummyDbSession()
    monkeypatch.setattr(settings, "TEXT2SQL_QUERY_LOG_ENABLED", True)

    monkeypatch.setattr(
        facade,
        "_run_pipeline",
        lambda **kwargs: {
            "generated_sql": "SELECT 1",
            "sql": "SELECT 1",
            "rows": [{"v": 1}],
            "selected_tables": ["t_demo"],
            "repaired": False,
            "relation_guard_used": False,
            "columns": ["v"],
            "answer": "1",
            "field_inference": [],
        },
    )

    result = facade.query("测试问题", db)

    assert result["sql"] == "SELECT 1"
    assert db.rollback_calls == 1


def test_query_keeps_original_error_when_failed_log_write_error(monkeypatch):
    facade = _build_facade(FailingFailedLogService())
    db = DummyDbSession()
    monkeypatch.setattr(settings, "TEXT2SQL_QUERY_LOG_ENABLED", True)

    def raise_pipeline_error(**kwargs):
        raise ValueError("pipeline failed")

    monkeypatch.setattr(facade, "_run_pipeline", raise_pipeline_error)

    with pytest.raises(ValueError, match="pipeline failed"):
        facade.query("测试问题", db)
    assert db.rollback_calls == 1
