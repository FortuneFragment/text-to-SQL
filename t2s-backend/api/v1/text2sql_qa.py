import logging

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from schemas.text2sql import (
    Text2SQLDebugGenerateResponse,
    Text2SQLQueryLogItem,
    Text2SQLQueryRequest,
    Text2SQLQueryResponse,
)
from services.text2sql import config_service, facade_service, log_service
from services.text2sql.facade_service import GLOBAL_QUERY_USER_ID

router = APIRouter(prefix="/qa", tags=["text2sql-qa"])
logger = logging.getLogger(__name__)


@router.post("/query", response_model=Text2SQLQueryResponse)
def query_text2sql(payload: Text2SQLQueryRequest, db: Session = Depends(get_db)):
    """把自然语言问题转成 SQL 并执行，返回查询结果。"""
    if not settings.TEXT2SQL_ENABLED:
        raise HTTPException(status_code=503, detail="\u5f53\u524d\u5df2\u7981\u7528 Text2SQL \u95ee\u7b54\u529f\u80fd")
    runtime_config = config_service.get_runtime_config(db)
    runtime_config["request_id"] = uuid4().hex[:8]
    try:
        result = facade_service.query(payload.question, db, runtime_config)
    except ValueError as exc:
        if str(exc) == "\u5927\u6a21\u578b\u4e0d\u53ef\u7528":
            raise HTTPException(status_code=422, detail="\u5927\u6a21\u578b\u4e0d\u53ef\u7528") from exc
        logger.exception("query validation failed")
        raise HTTPException(status_code=422, detail="\u67e5\u8be2\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u95ee\u9898\u6216\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("query failed")
        raise HTTPException(status_code=400, detail="\u67e5\u8be2\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u95ee\u9898\u6216\u7a0d\u540e\u91cd\u8bd5") from exc
    return Text2SQLQueryResponse(
        sql=result["sql"],
        columns=result["columns"],
        rows=result["rows"],
        answer=result["answer"],
        row_count=len(result["rows"]),
        repaired=bool(result.get("repaired")),
        field_inference=result.get("field_inference") or [],
    )

@router.post("/debug/generate", response_model=Text2SQLDebugGenerateResponse)
def debug_generate(payload: Text2SQLQueryRequest, db: Session = Depends(get_db)):
    """只做 SQL 生成与校验，便于调试路由和提示词。"""
    runtime_config = config_service.get_runtime_config(db)
    runtime_config["request_id"] = uuid4().hex[:8]
    try:
        result = facade_service.debug_generate(payload.question, db, runtime_config)
    except ValueError as exc:
        if str(exc) == "\u5927\u6a21\u578b\u4e0d\u53ef\u7528":
            raise HTTPException(status_code=422, detail="\u5927\u6a21\u578b\u4e0d\u53ef\u7528") from exc
        logger.exception("debug generate validation failed")
        raise HTTPException(status_code=422, detail="\u8c03\u8bd5\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u95ee\u9898\u6216\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("debug generate failed")
        raise HTTPException(status_code=400, detail="\u8c03\u8bd5\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u95ee\u9898\u6216\u7a0d\u540e\u91cd\u8bd5") from exc
    return Text2SQLDebugGenerateResponse(
        sql=result["sql"],
        validation_passed=bool(result["validation_passed"]),
        validation_message=str(result.get("validation_message") or ""),
        route_mode=str(result.get("mode") or ""),
        route_tables=[str(item) for item in (result.get("candidate_tables") or []) if str(item).strip()],
        route_pool_tables=[str(item) for item in (result.get("route_pool_tables") or []) if str(item).strip()],
        route_scores={
            str(name): float(score)
            for name, score in dict(result.get("route_scores") or {}).items()
            if str(name).strip()
        },
        relation_hints=[str(item) for item in (result.get("relation_hints") or []) if str(item).strip()],
        relation_guard_used=bool(result.get("relation_guard_used", False)),
    )

@router.get("/logs", response_model=list[Text2SQLQueryLogItem])
def get_logs(limit: int = 20, db: Session = Depends(get_db)):
    """按时间倒序返回最近的查询日志。"""
    safe_limit = max(1, min(limit, 100))
    return log_service.list_logs(db, GLOBAL_QUERY_USER_ID, safe_limit)
