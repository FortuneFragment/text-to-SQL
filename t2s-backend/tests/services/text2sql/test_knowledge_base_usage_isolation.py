from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.knowledge_usage import KB_USAGE_FEW_SHOT, KB_USAGE_TABLE_ROUTE
from models.knowledge_base import KnowledgeBase
from repositories.knowledge_base_repo import KnowledgeBaseRepository


_ROOT = Path(__file__).resolve().parents[3]


def _load_class(relative_path: str, class_name: str):
    spec = importlib.util.spec_from_file_location(
        f"{class_name}_under_test",
        _ROOT / relative_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


Text2SQLFewShotService = _load_class("services/text2sql/few_shot_service.py", "Text2SQLFewShotService")
Text2SQLVectorService = _load_class("services/text2sql/vector_service.py", "Text2SQLVectorService")


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.__table__.create(bind=engine)
    KnowledgeBaseRepository._usage_column_checked = False
    KnowledgeBaseRepository._usage_column_available = True
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        route_kb = KnowledgeBase(
            name="route",
            description="",
            collection_name="route_collection",
            usage=KB_USAGE_TABLE_ROUTE,
            is_default=True,
            is_deleted=False,
        )
        few_shot_kb = KnowledgeBase(
            name="few",
            description="",
            collection_name="few_collection",
            usage=KB_USAGE_FEW_SHOT,
            is_default=False,
            is_deleted=False,
        )
        db.add_all([route_kb, few_shot_kb])
        db.commit()
        db.refresh(route_kb)
        db.refresh(few_shot_kb)
        yield db, route_kb, few_shot_kb
    finally:
        db.close()
        engine.dispose()


def test_table_route_resolver_ignores_few_shot_kb(session):
    db, route_kb, few_shot_kb = session
    service = Text2SQLVectorService(kb_id=int(few_shot_kb.id))

    active_kb_id, kb = service._resolve_route_kb(db, requested_kb_id=int(few_shot_kb.id))

    assert active_kb_id == int(route_kb.id)
    assert kb.collection_name == "route_collection"


def test_few_shot_resolver_ignores_table_route_kb(session, monkeypatch):
    db, _route_kb, few_shot_kb = session
    monkeypatch.setattr(settings, "FEW_SHOT_KB_ID", 1)
    service = Text2SQLFewShotService()

    kb = service._resolve_few_shot_kb(db, create_if_missing=False)

    assert kb is not None
    assert int(kb.id) == int(few_shot_kb.id)
    assert kb.collection_name == "few_collection"
