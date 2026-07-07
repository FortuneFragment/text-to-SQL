from fastapi import APIRouter, Depends, HTTPException
import logging

from sqlalchemy.orm import Session

from core.database import get_db
from schemas.text2sql import (
    Text2SQLSchemaResponse,
    Text2SQLTableOption,
    Text2SQLTableOptionsResponse,
)
from services.text2sql import schema_service

router = APIRouter(prefix="/table", tags=["text2sql-table"])
logger = logging.getLogger(__name__)

@router.get("/schema", response_model=Text2SQLSchemaResponse)
def get_schema(db: Session = Depends(get_db)):
    """返回当前数据库可用表结构概览。"""
    try:
        return schema_service.list_schema_overview(db)
    except ValueError as exc:
        logger.exception("get schema validation failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u8868\u7ed3\u6784\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get schema failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u8868\u7ed3\u6784\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc

@router.get("/options", response_model=Text2SQLTableOptionsResponse)
def get_table_options(db: Session = Depends(get_db)):
    """返回当前数据库可用表列表。"""
    try:
        options = schema_service.list_table_options(db)
        return Text2SQLTableOptionsResponse(tables=[Text2SQLTableOption(**item) for item in options])
    except ValueError as exc:
        logger.exception("get table options validation failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u6570\u636e\u8868\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get table options failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u6570\u636e\u8868\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
