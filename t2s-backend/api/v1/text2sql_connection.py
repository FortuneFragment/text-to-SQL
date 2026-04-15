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


@router.get("", response_model=Text2SQLConnectionResponse)
def get_connection(db: Session = Depends(get_db)):
    """获取connection相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 返回结果：输出当前函数最终结果。
    return connection_service.get_public_connection(db)


@router.put("", response_model=Text2SQLConnectionResponse)
def save_connection(payload: Text2SQLConnectionPayload, db: Session = Depends(get_db)):
    """保存connection相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 核心处理：执行当前阶段的业务逻辑。
    try:
        return connection_service.save_connection(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u8fde\u63a5\u5931\u8d25: {exc}") from exc


@router.post("/test", response_model=Text2SQLConnectionTestResponse)
def test_connection(payload: Text2SQLConnectionPayload, db: Session = Depends(get_db)):
    """测试connection相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 核心处理：执行当前阶段的业务逻辑。
    try:
        connection_service.test_connection(db, payload)
        return Text2SQLConnectionTestResponse(ok=True, message="\u8fde\u63a5\u6d4b\u8bd5\u6210\u529f")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u8fde\u63a5\u6d4b\u8bd5\u5931\u8d25: {exc}") from exc
