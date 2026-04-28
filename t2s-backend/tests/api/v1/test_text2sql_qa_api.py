from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.v1 import text2sql_qa
from core.config import settings
from schemas.text2sql import Text2SQLQueryRequest


def test_query_endpoint_disabled_when_text2sql_disabled(monkeypatch):
    monkeypatch.setattr(settings, "TEXT2SQL_ENABLED", False)

    with pytest.raises(HTTPException) as exc_info:
        text2sql_qa.query_text2sql(Text2SQLQueryRequest(question="query anything"), db=None)

    assert exc_info.value.status_code == 503
    assert "\u7981\u7528" in str(exc_info.value.detail)
