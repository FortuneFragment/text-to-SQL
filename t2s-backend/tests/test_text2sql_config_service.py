import importlib
from types import SimpleNamespace

from schemas.text2sql import Text2SQLConnectionResponse, UpdateText2SQLConfigRequest
from services.text2sql.config_service import Text2SQLConfigService
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.schema_service import Text2SQLSchemaService


def _build_service() -> Text2SQLConfigService:
    connection_service = Text2SQLConnectionService()
    schema_service = Text2SQLSchemaService(connection_service)
    return Text2SQLConfigService(schema_service, connection_service)


def _mock_connection(configured: bool = True) -> Text2SQLConnectionResponse:
    return Text2SQLConnectionResponse(
        configured=configured,
        db_type="mysql" if configured else None,
        host="127.0.0.1" if configured else "",
        port=3306,
        username="root" if configured else "",
        database="school" if configured else "",
        charset="utf8mb4",
        has_password=True,
    )


def test_get_config_prefers_scoped(monkeypatch):
    service = _build_service()
    monkeypatch.setattr(service.connection_service, "get_public_connection", lambda db: _mock_connection(True))

    class ScopedRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user_and_connection(self, user_id, connection_key):
            assert connection_key == "mysql|127.0.0.1|3306|school|root"
            return SimpleNamespace(selected_tables='["t_student"]', prompt_hint="只查当前学年")

    class LegacyRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user_id(self, user_id):
            raise AssertionError("存在 scoped 配置时不应读取旧配置")

    module = importlib.import_module("services.text2sql.config_service")

    monkeypatch.setattr(module, "Text2SQLScopedConfigRepository", ScopedRepo)
    monkeypatch.setattr(module, "Text2SQLConfigRepository", LegacyRepo)

    config = service.get_config(object())
    assert config.selected_tables == ["t_student"]
    assert config.prompt_hint == "只查当前学年"


def test_get_config_falls_back_to_legacy(monkeypatch):
    service = _build_service()
    monkeypatch.setattr(service.connection_service, "get_public_connection", lambda db: _mock_connection(True))

    class ScopedRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user_and_connection(self, user_id, connection_key):
            return None

    class LegacyRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user_id(self, user_id):
            return SimpleNamespace(selected_tables='["legacy_table"]', prompt_hint="旧配置提示")

    module = importlib.import_module("services.text2sql.config_service")

    monkeypatch.setattr(module, "Text2SQLScopedConfigRepository", ScopedRepo)
    monkeypatch.setattr(module, "Text2SQLConfigRepository", LegacyRepo)

    config = service.get_config(object())
    assert config.selected_tables == ["legacy_table"]
    assert config.prompt_hint == "旧配置提示"


def test_update_config_writes_scoped_by_connection(monkeypatch):
    service = _build_service()
    monkeypatch.setattr(service.connection_service, "get_public_connection", lambda db: _mock_connection(True))
    monkeypatch.setattr(
        service.schema_service,
        "validate_selected_tables",
        lambda db, selected_tables: (selected_tables, []),
    )

    class ScopedRepo:
        store = {}

        def __init__(self, db):
            self.db = db

        def get_by_user_and_connection(self, user_id, connection_key):
            return self.store.get((user_id, connection_key))

        def upsert(self, *, user_id, connection_key, selected_tables, prompt_hint):
            record = SimpleNamespace(selected_tables=selected_tables, prompt_hint=prompt_hint)
            self.store[(user_id, connection_key)] = record
            return record

    class LegacyRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user_id(self, user_id):
            return None

    module = importlib.import_module("services.text2sql.config_service")

    monkeypatch.setattr(module, "Text2SQLScopedConfigRepository", ScopedRepo)
    monkeypatch.setattr(module, "Text2SQLConfigRepository", LegacyRepo)

    updated = service.update_config(
        object(),
        UpdateText2SQLConfigRequest(selected_tables=["t_score"], prompt_hint="按班级统计"),
    )
    assert updated.selected_tables == ["t_score"]
    assert updated.prompt_hint == "按班级统计"
