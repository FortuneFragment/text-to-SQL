from fastapi import APIRouter, Depends, HTTPException
import logging

from sqlalchemy.orm import Session

from core.database import get_db
from schemas.text2sql import (
    Text2SQLConfigResponse,
    Text2SQLSchemaResponse,
    Text2SQLTableFieldsResponse,
    Text2SQLTableOptionsResponse,
    UpdateText2SQLConfigRequest,
    UpdateText2SQLTableFieldsRequest,
)
from services.text2sql import config_service, field_permission_service, schema_service

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
    """返回可配置表开关的表列表。"""
    try:
        return field_permission_service.get_table_options(db)
    except ValueError as exc:
        logger.exception("get table options validation failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u6570\u636e\u8868\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get table options failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u6570\u636e\u8868\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc

@router.get("/config", response_model=Text2SQLConfigResponse)
def get_config(db: Session = Depends(get_db)):
    """读取当前连接下的表开关与提示词配置。"""
    return config_service.get_config(db)

@router.put("/config", response_model=Text2SQLConfigResponse)
def update_config(data: UpdateText2SQLConfigRequest, db: Session = Depends(get_db)):
    """保存当前连接下的表开关与提示词配置。"""
    try:
        return config_service.update_config(db, data)
    except ValueError as exc:
        logger.exception("update table config validation failed")
        raise HTTPException(status_code=400, detail="\u4fdd\u5b58\u914d\u7f6e\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("update table config failed")
        raise HTTPException(status_code=400, detail="\u4fdd\u5b58\u914d\u7f6e\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc

@router.get("/{table_name}/fields", response_model=Text2SQLTableFieldsResponse)
def get_table_fields(table_name: str, db: Session = Depends(get_db)):
    """读取指定表的字段开关配置。"""
    try:
        return field_permission_service.get_table_fields(db, table_name)
    except ValueError as exc:
        logger.exception("get table fields validation failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u5b57\u6bb5\u914d\u7f6e\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get table fields failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u5b57\u6bb5\u914d\u7f6e\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc

@router.put("/{table_name}/fields", response_model=Text2SQLTableFieldsResponse)
def update_table_fields(
    table_name: str,
    data: UpdateText2SQLTableFieldsRequest,
    db: Session = Depends(get_db),
):
    """更新指定表的字段开关配置。"""
    try:
        return field_permission_service.update_table_fields(db, table_name, data)
    except ValueError as exc:
        logger.exception("update table fields validation failed")
        raise HTTPException(status_code=400, detail="\u4fdd\u5b58\u5b57\u6bb5\u914d\u7f6e\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("update table fields failed")
        raise HTTPException(status_code=400, detail="\u4fdd\u5b58\u5b57\u6bb5\u914d\u7f6e\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
