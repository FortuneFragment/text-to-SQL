import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.text2sql import (
    Text2SQLConnectionPayload,
    Text2SQLConnectionResponse,
    Text2SQLConnectionTestResponse,
)
from services.text2sql import connection_service

router = APIRouter(prefix="/connection", tags=["text2sql-connection"])
logger = logging.getLogger(__name__)


@router.get("", response_model=Text2SQLConnectionResponse)
def get_connection(db: Session = Depends(get_db)):
    """返回当前生效的数据库连接配置（不包含密码）。"""
    return connection_service.get_public_connection(db)

@router.put("", response_model=Text2SQLConnectionResponse)
def save_connection(payload: Text2SQLConnectionPayload, db: Session = Depends(get_db)):
    """保存外部数据库连接配置，并切换到该连接。"""
    try:
        return connection_service.save_connection(db, payload)
    except ValueError as exc:
        logger.exception("save connection validation failed")
        raise HTTPException(status_code=400, detail="\u8fde\u63a5\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u914d\u7f6e\u6216\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("save connection failed")
        raise HTTPException(status_code=400, detail="\u8fde\u63a5\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u914d\u7f6e\u6216\u7a0d\u540e\u91cd\u8bd5") from exc

@router.post("/test", response_model=Text2SQLConnectionTestResponse)
def test_connection(payload: Text2SQLConnectionPayload, db: Session = Depends(get_db)):
    """仅测试连接参数是否可用，不会落库保存。"""
    try:
        connection_service.test_connection(db, payload)
        return Text2SQLConnectionTestResponse(ok=True, message="\u8fde\u63a5\u6d4b\u8bd5\u6210\u529f")
    except ValueError as exc:
        logger.exception("test connection validation failed")
        raise HTTPException(status_code=400, detail="\u8fde\u63a5\u6d4b\u8bd5\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u914d\u7f6e\u6216\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("test connection failed")
        raise HTTPException(status_code=400, detail="\u8fde\u63a5\u6d4b\u8bd5\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u914d\u7f6e\u6216\u7a0d\u540e\u91cd\u8bd5") from exc
