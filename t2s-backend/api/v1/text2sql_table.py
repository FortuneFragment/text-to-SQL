from fastapi import APIRouter, Depends, HTTPException
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

@router.get("/schema", response_model=Text2SQLSchemaResponse)
def get_schema(db: Session = Depends(get_db)):
    """返回当前数据库可用表结构概览。"""
    try:
        return schema_service.list_schema_overview(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u83b7\u53d6\u8868\u7ed3\u6784\u5931\u8d25: {exc}") from exc

@router.get("/options", response_model=Text2SQLTableOptionsResponse)
def get_table_options(db: Session = Depends(get_db)):
    """返回可配置表开关的表列表。"""
    try:
        return field_permission_service.get_table_options(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u83b7\u53d6\u6570\u636e\u8868\u5217\u8868\u5931\u8d25: {exc}") from exc

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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u4fdd\u5b58\u914d\u7f6e\u5931\u8d25: {exc}") from exc

@router.get("/{table_name}/fields", response_model=Text2SQLTableFieldsResponse)
def get_table_fields(table_name: str, db: Session = Depends(get_db)):
    """读取指定表的字段开关配置。"""
    try:
        return field_permission_service.get_table_fields(db, table_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u83b7\u53d6\u5b57\u6bb5\u914d\u7f6e\u5931\u8d25: {exc}") from exc

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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"\u4fdd\u5b58\u5b57\u6bb5\u914d\u7f6e\u5931\u8d25: {exc}") from exc
