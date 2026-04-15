from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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


@router.post("/query", response_model=Text2SQLQueryResponse)
def query_text2sql(payload: Text2SQLQueryRequest, db: Session = Depends(get_db)):
    """查询text2sql相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 变量构建：计算并更新 `runtime_config`。
    runtime_config = config_service.get_runtime_config(db)
    runtime_config["request_id"] = uuid4().hex[:8]
    # 2. 核心处理：执行当前阶段的业务逻辑。
    try:
        result = facade_service.query(payload.question, db, runtime_config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u67e5\u8be2\u5931\u8d25: {exc}") from exc

    # 3. 返回结果：输出当前函数最终结果。
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
    """中文备注：调试generate相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 变量构建：计算并更新 `runtime_config`。
    runtime_config = config_service.get_runtime_config(db)
    runtime_config["request_id"] = uuid4().hex[:8]
    # 2. 核心处理：执行当前阶段的业务逻辑。
    try:
        result = facade_service.debug_generate(payload.question, db, runtime_config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u8c03\u8bd5\u5931\u8d25: {exc}") from exc

    # 3. 返回结果：输出当前函数最终结果。
    return Text2SQLDebugGenerateResponse(
        sql=result["sql"],
        validation_passed=bool(result["validation_passed"]),
        validation_message=str(result.get("validation_message") or ""),
    )


@router.get("/logs", response_model=list[Text2SQLQueryLogItem])
def get_logs(limit: int = 20, db: Session = Depends(get_db)):
    """中文备注：获取logs相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 变量构建：计算并更新 `safe_limit`。
    safe_limit = max(1, min(limit, 100))
    # 2. 返回结果：输出当前函数最终结果。
    return log_service.list_logs(db, GLOBAL_QUERY_USER_ID, safe_limit)
