from __future__ import annotations

from types import SimpleNamespace

import anyio
import pytest
from fastapi import HTTPException

from api.v1 import text2sql_qa
from core.config import settings
from schemas.text2sql import Text2SQLQueryRequest


def test_query_endpoint_disabled_when_text2sql_disabled(monkeypatch):
    monkeypatch.setattr(settings, "TEXT2SQL_ENABLED", False)

    with pytest.raises(HTTPException) as exc_info:
        text2sql_qa.query_text2sql(
            Text2SQLQueryRequest(question="query anything"),
            db=None,
            current_user=SimpleNamespace(id=1),
        )

    assert exc_info.value.status_code == 503
    assert "\u7981\u7528" in str(exc_info.value.detail)


def test_query_endpoint_hides_raw_exception_detail(monkeypatch):
    monkeypatch.setattr(settings, "TEXT2SQL_ENABLED", True)
    monkeypatch.setattr(text2sql_qa.config_service, "get_runtime_config", lambda db, user_id=None: {})

    def fail_query(*args, **kwargs):
        raise ValueError("internal database secret")

    monkeypatch.setattr(text2sql_qa.facade_service, "query", fail_query)

    with pytest.raises(HTTPException) as exc_info:
        text2sql_qa.query_text2sql(
            Text2SQLQueryRequest(question="query anything"),
            db=None,
            current_user=SimpleNamespace(id=1),
        )

    assert exc_info.value.status_code == 422
    assert "internal database secret" not in str(exc_info.value.detail)
    assert "\u67e5\u8be2\u5931\u8d25" in str(exc_info.value.detail)


def test_query_stream_hides_raw_exception_detail(monkeypatch):
    monkeypatch.setattr(settings, "TEXT2SQL_ENABLED", True)
    monkeypatch.setattr(text2sql_qa.config_service, "get_runtime_config", lambda db, user_id=None: {})

    def fail_query(*args, **kwargs):
        raise RuntimeError("internal streaming secret")

    monkeypatch.setattr(text2sql_qa.facade_service, "query", fail_query)

    response = text2sql_qa.query_text2sql_stream(
        Text2SQLQueryRequest(question="query anything"),
        current_user=SimpleNamespace(id=1),
    )
    chunks: list[str] = []

    async def collect_stream() -> None:
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)

    anyio.run(collect_stream)
    body = "".join(chunks)

    assert "internal streaming secret" not in body
    assert "\u67e5\u8be2\u5931\u8d25" in body
