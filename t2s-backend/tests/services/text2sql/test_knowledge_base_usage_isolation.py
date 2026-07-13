from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.domain_errors import (
    KnowledgeBaseConfigurationError,
    KnowledgeOperationForbiddenError,
)
from core.knowledge_usage import KB_USAGE_FEW_SHOT, KB_USAGE_TABLE_ROUTE
from models.knowledge_base import KnowledgeBase
from repositories.knowledge_base_repo import KnowledgeBaseRepository


_ROOT = Path(__file__).resolve().parents[3]
import sys
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


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
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        route_kb = KnowledgeBase(
            name="route",
            description="",
            collection_name="route_collection",
            usage=KB_USAGE_TABLE_ROUTE,
        )
        few_shot_kb = KnowledgeBase(
            name="few",
            description="",
            collection_name="few_collection",
            usage=KB_USAGE_FEW_SHOT,
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

    with pytest.raises(KnowledgeOperationForbiddenError):
        service._resolve_route_kb(db, requested_kb_id=int(few_shot_kb.id))


def test_table_route_resolver_does_not_select_first_kb(session):
    db, _route_kb, _few_shot_kb = session
    service = Text2SQLVectorService(kb_id=0)

    assert service._resolve_route_kb(db) == (0, None)


def test_few_shot_resolver_ignores_table_route_kb(session, monkeypatch):
    db, _route_kb, few_shot_kb = session
    monkeypatch.setattr(settings, "FEW_SHOT_KB_ID", 1)
    service = Text2SQLFewShotService()

    with pytest.raises(KnowledgeOperationForbiddenError):
        service._resolve_few_shot_kb(db)


def test_few_shot_resolver_requires_explicit_kb_id(session, monkeypatch):
    db, _route_kb, _few_shot_kb = session
    monkeypatch.setattr(settings, "FEW_SHOT_KB_ID", 0)
    service = Text2SQLFewShotService()

    with pytest.raises(KnowledgeBaseConfigurationError, match="FEW_SHOT_KB_ID"):
        service._resolve_few_shot_kb(db)
