from __future__ import annotations

from core.config import settings
from services.text2sql.facade_service import Text2SQLFacadeService


class DummyConnectionService:
    def get_engine(self, db):
        return None


class DummySchemaService:
    def __init__(self):
        self.list_table_names_calls = 0
        self.list_table_options_by_names_calls: list[list[str]] = []

    def list_table_names(self, db):
        self.list_table_names_calls += 1
        return ["t_order", "t_customer", "t_product"]

    def list_table_options_by_names(self, db, table_names):
        self.list_table_options_by_names_calls.append(list(table_names or []))
        return [
            {"table_name": "t_order", "table_comment": "order"},
            {"table_name": "t_customer", "table_comment": "customer"},
            {"table_name": "t_product", "table_comment": "product"},
        ]

    def validate_selected_tables(self, db, table_names):
        return table_names or [], []

    def get_live_table_columns_map(self, db, table_names=None, queryable_columns_map=None):
        return {}


class DummyConfigService:
    pass


class DummyFieldPermissionService:
    def __init__(self):
        self.queryable_scope_calls: list[list[str] | None] = []

    def get_queryable_table_names(self, db, table_names=None):
        self.queryable_scope_calls.append(list(table_names) if table_names is not None else None)
        return ["t_order", "t_customer", "t_product"]

    def get_queryable_columns_map(self, db, table_names=None):
        return {
            "t_order": {"id", "customer_id", "amount"},
            "t_customer": {"id", "name"},
            "t_product": {"id", "name"},
        }

    def build_query_field_comment_bindings(self, **kwargs):
        return []


class DummyRelationService:
    def get_active_relations_by_tables(self, db, table_names):
        return []

    @staticmethod
    def relation_hint_lines(relation_hints):
        return []


class DummyLogService:
    def create_success_log(self, **kwargs):
        return None

    def create_failed_log(self, **kwargs):
        return None


def _build_facade():
    schema = DummySchemaService()
    field_permission = DummyFieldPermissionService()
    facade = Text2SQLFacadeService(
        connection_service=DummyConnectionService(),
        schema_service=schema,
        config_service=DummyConfigService(),
        field_permission_service=field_permission,
        relation_service=DummyRelationService(),
        log_service=DummyLogService(),
    )
    return facade, schema, field_permission


def test_route_tables_prefers_kb_recall_then_schema_rerank(monkeypatch):
    facade, schema, field_permission = _build_facade()
    monkeypatch.setattr(settings, "TABLE_ROUTE_KB_SEARCH_TOP_K", 50)
    monkeypatch.setattr(settings, "TABLE_ROUTE_KB_RECALL_CANDIDATES", 2)
    monkeypatch.setattr(settings, "TABLE_ROUTE_MAX_CANDIDATES", 2)
    monkeypatch.setattr(settings, "TEXT2SQL_MULTI_TABLE_ENABLED", True)
    monkeypatch.setattr(settings, "TEXT2SQL_MAX_JOIN_TABLES", 2)
    monkeypatch.setattr(settings, "TABLE_ROUTE_KB_ID", 0)

    vector_call_index = {"value": 0}

    def fake_search_tables(db, question, *, candidate_tables, top_k, candidate_profiles=None, route_kb_id=None):
        vector_call_index["value"] += 1
        if vector_call_index["value"] == 1:
            assert candidate_tables == ["t_order", "t_customer", "t_product"]
            assert candidate_profiles is None
            return {"t_order": 0.9, "t_customer": 0.8, "t_product": 0.2}
        assert candidate_tables == ["t_order", "t_customer"]
        assert isinstance(candidate_profiles, dict)
        return {"t_order": 0.88, "t_customer": 0.79}

    monkeypatch.setattr(facade.vector_service, "search_tables", fake_search_tables)
    monkeypatch.setattr(
        facade,
        "_llm_route_tables",
        lambda question, candidates, **kwargs: ["t_order", "t_customer"],
    )
    monkeypatch.setattr(
        facade.relation_service,
        "get_active_relations_by_tables",
        lambda db, table_names: [
            {
                "source_table": "t_order",
                "source_columns": ["customer_id"],
                "target_table": "t_customer",
                "target_columns": ["id"],
            }
        ]
        if {"t_order", "t_customer"}.issubset(set(table_names or []))
        else [],
    )

    route = facade._route_tables(
        db=object(),
        question="query orders and customers in the last 30 days",
        selected_tables=[],
    )

    assert vector_call_index["value"] == 2
    assert schema.list_table_names_calls == 1
    assert schema.list_table_options_by_names_calls[0] == ["t_order", "t_customer"]
    assert schema.list_table_options_by_names_calls[-1] == ["t_order", "t_customer"]
    assert field_permission.queryable_scope_calls == [["t_order", "t_customer", "t_product"]]
    assert route["mode"] == "multi"
    assert route["route_pool_tables"] == ["t_order", "t_customer"]
    assert route["candidates"] == ["t_order", "t_customer"]


def test_route_tables_expands_bridge_table_before_router(monkeypatch):
    facade, _, _ = _build_facade()
    monkeypatch.setattr(settings, "TABLE_ROUTE_KB_SEARCH_TOP_K", 50)
    monkeypatch.setattr(settings, "TABLE_ROUTE_KB_RECALL_CANDIDATES", 2)
    monkeypatch.setattr(settings, "TABLE_ROUTE_MAX_CANDIDATES", 2)
    monkeypatch.setattr(settings, "TEXT2SQL_MULTI_TABLE_ENABLED", True)
    monkeypatch.setattr(settings, "TEXT2SQL_MAX_JOIN_TABLES", 3)
    monkeypatch.setattr(settings, "TABLE_ROUTE_KB_ID", 0)

    vector_call_index = {"value": 0}

    def fake_search_tables(db, question, *, candidate_tables, top_k, candidate_profiles=None, route_kb_id=None):
        vector_call_index["value"] += 1
        if vector_call_index["value"] == 1:
            return {"t_order": 0.91, "t_product": 0.82}
        return {"t_order": 0.88, "t_product": 0.79}

    def fake_relation_hints(db, table_names):
        normalized_tables = {str(item).strip().lower() for item in (table_names or [])}
        hints = [
            {
                "source_table": "t_order",
                "source_columns": ["id"],
                "target_table": "t_customer",
                "target_columns": ["id"],
            },
            {
                "source_table": "t_customer",
                "source_columns": ["id"],
                "target_table": "t_product",
                "target_columns": ["id"],
            },
        ]
        if not normalized_tables:
            return []
        filtered: list[dict] = []
        for hint in hints:
            left = str(hint["source_table"]).lower()
            right = str(hint["target_table"]).lower()
            if left in normalized_tables and right in normalized_tables:
                filtered.append(dict(hint))
        return filtered

    router_seen = {"candidates": []}

    def fake_router(question, candidates, **kwargs):
        router_seen["candidates"] = list(candidates)
        return ["t_order", "t_customer", "t_product"]

    monkeypatch.setattr(facade.vector_service, "search_tables", fake_search_tables)
    monkeypatch.setattr(facade.relation_service, "get_active_relations_by_tables", fake_relation_hints)
    monkeypatch.setattr(facade, "_llm_route_tables", fake_router)

    route = facade._route_tables(
        db=object(),
        question="query order and product with relation bridge",
        selected_tables=[],
    )

    assert "t_customer" in router_seen["candidates"]
    assert route["route_pool_tables"] == ["t_order", "t_product", "t_customer"]
    assert route["candidates"] == ["t_order", "t_customer", "t_product"]


def test_route_tables_returns_no_signal_when_kb_and_keyword_have_no_hit(monkeypatch):
    facade, _, _ = _build_facade()
    monkeypatch.setattr(settings, "TABLE_ROUTE_KB_SEARCH_TOP_K", 50)
    monkeypatch.setattr(settings, "TABLE_ROUTE_KB_RECALL_CANDIDATES", 2)
    monkeypatch.setattr(settings, "TABLE_ROUTE_KB_ID", 0)

    monkeypatch.setattr(
        facade.vector_service,
        "search_tables",
        lambda db, question, *, candidate_tables, top_k, candidate_profiles=None, route_kb_id=None: {},
    )
    monkeypatch.setattr(
        facade,
        "_score_table_name_candidates",
        lambda question, table_names: {name: 0.0 for name in table_names},
    )

    route = facade._route_tables(
        db=object(),
        question="an unrelated question",
        selected_tables=[],
    )

    assert route["mode"] == "no_signal"
    assert route["candidates"] == []
    assert str(route.get("clarify_question") or "").strip()
