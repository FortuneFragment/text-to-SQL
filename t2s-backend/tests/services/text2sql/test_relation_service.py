from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.text2sql_table_relation import Text2SQLTableRelation
from schemas.text2sql import CreateText2SQLRelationRequest, UpdateText2SQLRelationRequest
from services.text2sql.relation_service import Text2SQLRelationService


class DummyConfigService:
    def __init__(self, connection_key: str = "mysql|127.0.0.1|3306|demo|root"):
        self.connection_key = connection_key

    def get_connection_key(self, db: Session) -> str:
        return self.connection_key


class DummySchemaService:
    def __init__(self):
        self._tables = {
            "t_user": {"id", "tenant_id", "name"},
            "t_order": {"id", "tenant_id", "user_id", "order_no"},
        }

    @staticmethod
    def _normalize(value: str | None) -> str:
        return str(value or "").strip().lower()

    def validate_selected_tables(self, db: Session, table_names: list[str] | None):
        if table_names is None:
            return sorted(self._tables.keys()), []
        resolved: list[str] = []
        missing: list[str] = []
        lookup = {self._normalize(name): name for name in self._tables.keys()}
        for item in table_names:
            real_name = lookup.get(self._normalize(item))
            if real_name:
                resolved.append(real_name)
            else:
                missing.append(str(item))
        return resolved, missing

    def get_table_detail(self, db: Session, table_name: str):
        columns = self._tables.get(table_name, set())
        return {
            "table_name": table_name,
            "table_comment": "",
            "columns": [{"name": name, "type": "varchar", "comment": ""} for name in sorted(columns)],
        }


def _build_db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Text2SQLTableRelation.__table__.create(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return session_factory()


def test_relation_service_crud_and_relation_hints():
    db = _build_db_session()
    service = Text2SQLRelationService(DummySchemaService(), DummyConfigService())
    created = service.create_relation(
        db,
        CreateText2SQLRelationRequest(
            source_table="t_order",
            source_columns=["tenant_id", "user_id"],
            target_table="t_user",
            target_columns=["tenant_id", "id"],
            relation_type="N:1",
            description="订单关联用户",
        ),
    )

    assert created.id > 0
    assert created.source_columns == ["tenant_id", "user_id"]
    assert created.target_columns == ["tenant_id", "id"]

    listing = service.list_relations(db, page=1, page_size=20)
    assert listing.total == 1
    assert len(listing.items) == 1

    hints = service.get_active_relations_by_tables(db, ["t_order", "t_user"])
    assert len(hints) == 1
    assert "t_order.user_id = t_user.id" in hints[0]["summary"]

    updated = service.update_relation(
        db,
        created.id,
        UpdateText2SQLRelationRequest(
            source_table="t_order",
            source_columns=["tenant_id", "user_id"],
            target_table="t_user",
            target_columns=["tenant_id", "id"],
            relation_type="N:1",
            description="已停用",
        ),
    )
    assert updated.description

    hints_after_update = service.get_active_relations_by_tables(db, ["t_order", "t_user"])
    assert len(hints_after_update) == 1

    service.delete_relation(db, created.id)
    after_delete = service.list_relations(db, page=1, page_size=20)
    assert after_delete.total == 0


def test_relation_service_rejects_duplicate_or_reverse_duplicate():
    db = _build_db_session()
    service = Text2SQLRelationService(DummySchemaService(), DummyConfigService())

    service.create_relation(
        db,
        CreateText2SQLRelationRequest(
            source_table="t_order",
            source_columns=["user_id"],
            target_table="t_user",
            target_columns=["id"],
            relation_type="N:1",
            description="",
        ),
    )
    with pytest.raises(ValueError):
        service.create_relation(
            db,
            CreateText2SQLRelationRequest(
                source_table="t_user",
                source_columns=["id"],
                target_table="t_order",
                target_columns=["user_id"],
                relation_type="1:N",
                description="反向重复",
            ),
        )


def test_relation_service_isolated_by_connection_key():
    db = _build_db_session()
    config_service = DummyConfigService(connection_key="conn-a")
    service = Text2SQLRelationService(DummySchemaService(), config_service)
    service.create_relation(
        db,
        CreateText2SQLRelationRequest(
            source_table="t_order",
            source_columns=["user_id"],
            target_table="t_user",
            target_columns=["id"],
            relation_type="N:1",
            description="",
        ),
    )

    config_service.connection_key = "conn-b"
    listing = service.list_relations(db, page=1, page_size=20)
    assert listing.total == 0


def test_relation_service_validates_composite_column_length():
    db = _build_db_session()
    service = Text2SQLRelationService(DummySchemaService(), DummyConfigService())
    with pytest.raises(ValueError):
        service.create_relation(
            db,
            CreateText2SQLRelationRequest(
                source_table="t_order",
                source_columns=["tenant_id", "user_id"],
                target_table="t_user",
                target_columns=["tenant_id"],
                relation_type="N:1",
                description="",
            ),
        )
