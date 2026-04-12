from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.text2sql import (
    Text2SQLConfigResponse,
    Text2SQLConnectionPayload,
    Text2SQLConnectionResponse,
    Text2SQLConnectionTestResponse,
    Text2SQLDebugGenerateResponse,
    Text2SQLQueryLogItem,
    Text2SQLQueryRequest,
    Text2SQLQueryResponse,
    Text2SQLSchemaResponse,
    UpdateText2SQLConfigRequest,
)
from services.text2sql import config_service, connection_service, facade_service, log_service
from services.text2sql.facade_service import GLOBAL_QUERY_USER_ID

router = APIRouter(prefix="/text2sql", tags=["text2sql"])


@router.get("/connection", response_model=Text2SQLConnectionResponse)
def get_connection(db: Session = Depends(get_db)):
    return connection_service.get_public_connection(db)


@router.put("/connection", response_model=Text2SQLConnectionResponse)
def save_connection(payload: Text2SQLConnectionPayload, db: Session = Depends(get_db)):
    try:
        return connection_service.save_connection(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u8fde\u63a5\u5931\u8d25: {exc}") from exc


@router.post("/connection/test", response_model=Text2SQLConnectionTestResponse)
def test_connection(payload: Text2SQLConnectionPayload):
    try:
        connection_service.test_connection(payload)
        return Text2SQLConnectionTestResponse(ok=True, message="\u8fde\u63a5\u6d4b\u8bd5\u6210\u529f")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u8fde\u63a5\u6d4b\u8bd5\u5931\u8d25: {exc}") from exc


@router.get("/schema", response_model=Text2SQLSchemaResponse)
def get_schema(db: Session = Depends(get_db)):
    try:
        return facade_service.list_schema_overview(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u83b7\u53d6\u8868\u7ed3\u6784\u5931\u8d25: {exc}") from exc


@router.get("/config", response_model=Text2SQLConfigResponse)
def get_config(db: Session = Depends(get_db)):
    return config_service.get_config(db)


@router.put("/config", response_model=Text2SQLConfigResponse)
def update_config(data: UpdateText2SQLConfigRequest, db: Session = Depends(get_db)):
    try:
        return config_service.update_config(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u4fdd\u5b58\u914d\u7f6e\u5931\u8d25: {exc}") from exc


@router.post("/query", response_model=Text2SQLQueryResponse)
def query_text2sql(payload: Text2SQLQueryRequest, db: Session = Depends(get_db)):
    runtime_config = config_service.get_runtime_config(db)
    runtime_config["request_id"] = uuid4().hex[:8]
    try:
        result = facade_service.query(payload.question, db, runtime_config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u67e5\u8be2\u5931\u8d25: {exc}") from exc

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
    runtime_config = config_service.get_runtime_config(db)
    runtime_config["request_id"] = uuid4().hex[:8]
    try:
        result = facade_service.debug_generate(payload.question, db, runtime_config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u8c03\u8bd5\u5931\u8d25: {exc}") from exc

    return Text2SQLDebugGenerateResponse(
        sql=result["sql"],
        validation_passed=bool(result["validation_passed"]),
        validation_message=str(result.get("validation_message") or ""),
    )


@router.get("/logs", response_model=list[Text2SQLQueryLogItem])
def get_logs(limit: int = 20, db: Session = Depends(get_db)):
    safe_limit = max(1, min(limit, 100))
    return log_service.list_logs(db, GLOBAL_QUERY_USER_ID, safe_limit)
