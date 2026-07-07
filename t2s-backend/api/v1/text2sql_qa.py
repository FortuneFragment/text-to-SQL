import json
import logging
from collections.abc import Generator
from queue import Queue
from threading import Thread
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal, get_db
from schemas.text2sql import (
    Text2SQLDebugGenerateResponse,
    Text2SQLFeedbackRequest,
    Text2SQLQueryLogItem,
    Text2SQLQueryRequest,
    Text2SQLQueryResponse,
)
from services.text2sql import config_service, facade_service, log_service
from services.text2sql.facade_service import GLOBAL_QUERY_USER_ID

router = APIRouter(prefix="/qa", tags=["text2sql-qa"])
alias_router = APIRouter(tags=["text2sql-query"])
logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _build_query_response(payload: dict) -> Text2SQLQueryResponse:
    rows = list(payload.get("rows") or [])
    return Text2SQLQueryResponse(
        sql=str(payload.get("sql") or ""),
        columns=list(payload.get("columns") or []),
        rows=rows,
        decoded_rows=list(payload.get("decoded_rows") or rows),
        answer=str(payload.get("answer") or ""),
        row_count=len(rows),
        repaired=bool(payload.get("repaired", False)),
        field_inference=list(payload.get("field_inference") or []),
        log_id=payload.get("log_id"),
        clarification=str(payload.get("clarification") or ""),
    )


def _build_debug_response(payload: dict) -> Text2SQLDebugGenerateResponse:
    return Text2SQLDebugGenerateResponse(
        sql=str(payload.get("sql") or ""),
        validation_passed=bool(payload.get("validation_passed", False)),
        validation_message=str(payload.get("validation_message") or ""),
        route_mode=str(payload.get("mode") or ""),
        route_tables=list(payload.get("candidate_tables") or payload.get("selected_tables") or []),
        route_pool_tables=list(payload.get("route_pool_tables") or []),
        route_scores={str(name): float(score) for name, score in dict(payload.get("route_scores") or {}).items()},
        relation_hints=[str(item) for item in (payload.get("relation_hints") or []) if str(item).strip()],
        relation_guard_used=bool(payload.get("relation_guard_used", False)),
    )


def _runtime_config_with_history(db: Session, request: Text2SQLQueryRequest) -> dict:
    runtime_config = config_service.get_runtime_config(db, user_id=GLOBAL_QUERY_USER_ID)
    runtime_config["request_id"] = uuid4().hex[:8]
    runtime_config["history"] = [turn.model_dump() for turn in request.history]
    return runtime_config


def _is_llm_unavailable(exc: ValueError) -> bool:
    return exc.args[:1] == ("大模型不可用",)


@router.post("/query", response_model=Text2SQLQueryResponse)
@alias_router.post("/query", response_model=Text2SQLQueryResponse)
def query_text2sql(payload: Text2SQLQueryRequest, db: Session = Depends(get_db)):
    """Convert a natural-language question to SQL, execute it, and return the answer."""
    if not settings.TEXT2SQL_ENABLED:
        raise HTTPException(status_code=503, detail="当前已禁用 Text2SQL 问答功能")
    runtime_config = _runtime_config_with_history(db, payload)
    try:
        result = facade_service.query(
            payload.question,
            db,
            runtime_config=runtime_config,
            user_id=GLOBAL_QUERY_USER_ID,
        )
    except ValueError as exc:
        if _is_llm_unavailable(exc):
            raise HTTPException(status_code=422, detail="大模型不可用") from exc
        logger.exception("query validation failed")
        raise HTTPException(status_code=422, detail="查询失败，请检查问题或稍后重试") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("query failed")
        raise HTTPException(status_code=400, detail="查询失败，请检查问题或稍后重试") from exc
    return _build_query_response(result)


@router.post("/query/feedback", response_model=bool)
@alias_router.post("/query/feedback", response_model=bool)
def query_feedback(payload: Text2SQLFeedbackRequest, db: Session = Depends(get_db)):
    """Record a 1-5 score for a query log; high-score logs can be reused as few-shot examples."""
    try:
        updated = log_service.update_feedback(
            db,
            log_id=payload.log_id,
            user_id=GLOBAL_QUERY_USER_ID,
            score=payload.score,
            answer=payload.answer,
            question=payload.question,
            sql=payload.sql,
            selected_tables=payload.selected_tables,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("feedback update failed")
        raise HTTPException(status_code=400, detail="反馈写入失败") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="日志不存在或无权修改")
    return True


@router.post("/query/stream")
@alias_router.post("/query/stream")
def query_text2sql_stream(payload: Text2SQLQueryRequest):
    """SSE streaming query with progress events and streaming summary chunks."""
    if not settings.TEXT2SQL_ENABLED:
        raise HTTPException(status_code=503, detail="当前已禁用 Text2SQL 问答功能")

    def event_stream() -> Generator[str, None, None]:
        queue: Queue[tuple[str, dict] | None] = Queue()

        def emit_progress(event: str, data: dict) -> None:
            queue.put((event, data))

        def worker() -> None:
            db = SessionLocal()
            try:
                runtime_config = _runtime_config_with_history(db, payload)
                emit_progress("status", {"step": "routing", "message": "正在选择候选表..."})
                result = facade_service.query(
                    payload.question,
                    db,
                    runtime_config=runtime_config,
                    user_id=GLOBAL_QUERY_USER_ID,
                    progress_callback=emit_progress,
                )
                emit_progress("status", {"step": "completed", "message": "查询完成"})
                emit_progress("done", _build_query_response(result).model_dump())
            except Exception as exc:  # noqa: BLE001
                logger.exception("stream query failed")
                emit_progress("error", {"message": "查询失败，请检查问题或稍后重试"})
            finally:
                db.close()
                queue.put(None)

        Thread(target=worker, daemon=True).start()
        while True:
            item = queue.get()
            if item is None:
                break
            event, data = item
            yield _sse(event, data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/debug/generate", response_model=Text2SQLDebugGenerateResponse)
@alias_router.post("/debug/generate", response_model=Text2SQLDebugGenerateResponse)
def debug_generate(payload: Text2SQLQueryRequest, db: Session = Depends(get_db)):
    """Generate and validate SQL without executing it."""
    runtime_config = _runtime_config_with_history(db, payload)
    try:
        result = facade_service.debug_generate(
            payload.question,
            db,
            runtime_config=runtime_config,
            user_id=GLOBAL_QUERY_USER_ID,
        )
    except ValueError as exc:
        if _is_llm_unavailable(exc):
            raise HTTPException(status_code=422, detail="大模型不可用") from exc
        logger.exception("debug generate validation failed")
        raise HTTPException(status_code=422, detail="调试失败，请检查问题或稍后重试") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("debug generate failed")
        raise HTTPException(status_code=400, detail="调试失败，请检查问题或稍后重试") from exc
    return _build_debug_response(result)


@router.post("/debug/generate/stream")
@alias_router.post("/debug/generate/stream")
def debug_generate_stream(payload: Text2SQLQueryRequest):
    """SSE streaming debug generation."""
    if not settings.TEXT2SQL_ENABLED:
        raise HTTPException(status_code=503, detail="当前已禁用 Text2SQL 问答功能")

    def event_stream() -> Generator[str, None, None]:
        queue: Queue[tuple[str, dict] | None] = Queue()

        def emit_progress(event: str, data: dict) -> None:
            queue.put((event, data))

        def worker() -> None:
            db = SessionLocal()
            try:
                runtime_config = _runtime_config_with_history(db, payload)
                emit_progress("status", {"step": "routing", "message": "正在选择候选表..."})
                result = facade_service.debug_generate(
                    payload.question,
                    db,
                    runtime_config=runtime_config,
                    user_id=GLOBAL_QUERY_USER_ID,
                    progress_callback=emit_progress,
                )
                emit_progress("status", {"step": "completed", "message": "SQL 生成完成"})
                emit_progress("done", _build_debug_response(result).model_dump())
            except Exception as exc:  # noqa: BLE001
                logger.exception("stream debug generate failed")
                emit_progress("error", {"message": "调试失败，请检查问题或稍后重试"})
            finally:
                db.close()
                queue.put(None)

        Thread(target=worker, daemon=True).start()
        while True:
            item = queue.get()
            if item is None:
                break
            event, data = item
            yield _sse(event, data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/logs", response_model=list[Text2SQLQueryLogItem])
@alias_router.get("/logs", response_model=list[Text2SQLQueryLogItem])
def get_logs(limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)):
    """Return recent query logs in reverse chronological order."""
    return log_service.list_logs(db, GLOBAL_QUERY_USER_ID, limit)
