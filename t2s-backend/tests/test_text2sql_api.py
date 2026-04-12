import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from core.database import get_db
from schemas.text2sql import (
    Text2SQLConfigResponse,
    Text2SQLConnectionResponse,
    Text2SQLQueryLogItem,
    Text2SQLSchemaResponse,
)

os.environ.setdefault("STARTUP_WAIT_ENABLED", "false")

from core.config import settings

settings.STARTUP_WAIT_ENABLED = False

from main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    def _override_get_db():
        yield object()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_connection(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from api.v1 import text2sql as route

    monkeypatch.setattr(
        route.connection_service,
        "get_public_connection",
        lambda db: Text2SQLConnectionResponse(
            configured=True,
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            username="root",
            database="demo",
            charset="utf8mb4",
            has_password=True,
        ),
    )

    resp = client.get("/api/v1/text2sql/connection")
    assert resp.status_code == 200
    assert resp.json()["configured"] is True


def test_get_schema(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from api.v1 import text2sql as route

    monkeypatch.setattr(
        route.facade_service,
        "list_schema_overview",
        lambda db: Text2SQLSchemaResponse(
            tables=[
                {
                    "table_name": "student_scores",
                    "columns": [{"name": "id", "type": "BIGINT"}],
                }
            ]
        ),
    )

    resp = client.get("/api/v1/text2sql/schema")
    assert resp.status_code == 200
    assert resp.json()["tables"][0]["table_name"] == "student_scores"


def test_update_config(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from api.v1 import text2sql as route

    monkeypatch.setattr(
        route.config_service,
        "update_config",
        lambda db, payload: Text2SQLConfigResponse(
            selected_tables=payload.selected_tables,
            prompt_hint=payload.prompt_hint,
        ),
    )

    resp = client.put(
        "/api/v1/text2sql/config",
        json={"selected_tables": ["student_scores"], "prompt_hint": "只查期中考试"},
    )
    assert resp.status_code == 200
    assert resp.json()["selected_tables"] == ["student_scores"]


def test_query(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from api.v1 import text2sql as route

    monkeypatch.setattr(route.config_service, "get_runtime_config", lambda db: {"selected_tables": [], "prompt_hint": ""})
    monkeypatch.setattr(
        route.facade_service,
        "query",
        lambda question, db, runtime_config: {
            "sql": "SELECT id FROM student_scores LIMIT 10;",
            "columns": ["id"],
            "rows": [{"id": 1}],
            "answer": "共 1 行",
            "repaired": False,
            "field_inference": [
                {
                    "column": "id",
                    "inferred_meaning": "主键",
                    "confidence": 0.95,
                    "reason": "样例值唯一",
                }
            ],
        },
    )

    resp = client.post("/api/v1/text2sql/query", json={"question": "查一条数据"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["sql"].startswith("SELECT")
    assert payload["row_count"] == 1
    assert payload["field_inference"][0]["column"] == "id"


def test_logs(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from api.v1 import text2sql as route

    monkeypatch.setattr(
        route.log_service,
        "list_logs",
        lambda db, user_id, limit: [
            Text2SQLQueryLogItem(
                id=1,
                question="test",
                generated_sql="SELECT 1;",
                final_sql="SELECT 1;",
                status="success",
                error_message=None,
                row_count=1,
                duration_ms=20,
                repaired=False,
                created_at="2026-04-10T00:00:00",
            )
        ],
    )

    resp = client.get("/api/v1/text2sql/logs?limit=5")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

