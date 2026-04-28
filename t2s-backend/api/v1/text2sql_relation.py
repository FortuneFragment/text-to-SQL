from fastapi import APIRouter, Depends, HTTPException, Response, status
import logging

from sqlalchemy.orm import Session

from core.database import get_db
from schemas.text2sql import (
    CreateText2SQLRelationRequest,
    Text2SQLRelationItem,
    Text2SQLRelationListResponse,
    Text2SQLRelationTableColumnsResponse,
    UpdateText2SQLRelationRequest,
)
from services.text2sql import relation_service

router = APIRouter(prefix="/relation", tags=["text2sql-relation"])
logger = logging.getLogger(__name__)


@router.get("", response_model=Text2SQLRelationListResponse)
def list_relations(
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    table_name: str = "",
    db: Session = Depends(get_db),
):
    """分页读取当前连接下的关系配置。"""
    try:
        return relation_service.list_relations(
            db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            table_name=table_name,
        )
    except ValueError as exc:
        logger.exception("list relations validation failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u5173\u7cfb\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("list relations failed")
        raise HTTPException(status_code=400, detail="\u83b7\u53d6\u5173\u7cfb\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc


@router.post("", response_model=Text2SQLRelationItem)
def create_relation(payload: CreateText2SQLRelationRequest, db: Session = Depends(get_db)):
    """创建一条表关联关系。"""
    try:
        return relation_service.create_relation(db, payload)
    except ValueError as exc:
        logger.exception("create relation validation failed")
        raise HTTPException(status_code=400, detail="\u521b\u5efa\u5173\u7cfb\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("create relation failed")
        raise HTTPException(status_code=400, detail="\u521b\u5efa\u5173\u7cfb\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc


@router.put("/{relation_id}", response_model=Text2SQLRelationItem)
def update_relation(
    relation_id: int,
    payload: UpdateText2SQLRelationRequest,
    db: Session = Depends(get_db),
):
    """更新一条表关联关系。"""
    try:
        return relation_service.update_relation(db, relation_id, payload)
    except ValueError as exc:
        logger.exception("update relation validation failed")
        raise HTTPException(status_code=400, detail="\u66f4\u65b0\u5173\u7cfb\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("update relation failed")
        raise HTTPException(status_code=400, detail="\u66f4\u65b0\u5173\u7cfb\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc


@router.delete("/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(relation_id: int, db: Session = Depends(get_db)):
    """删除一条关系配置。"""
    try:
        relation_service.delete_relation(db, relation_id)
    except ValueError as exc:
        logger.exception("delete relation validation failed")
        raise HTTPException(status_code=400, detail="\u5220\u9664\u5173\u7cfb\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete relation failed")
        raise HTTPException(status_code=400, detail="\u5220\u9664\u5173\u7cfb\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/table/{table_name}/columns", response_model=Text2SQLRelationTableColumnsResponse)
def list_table_columns(table_name: str, db: Session = Depends(get_db)):
    """读取关系配置页需要的表字段列表。"""
    try:
        return relation_service.get_table_columns(db, table_name)
    except ValueError as exc:
        logger.exception("list relation table columns validation failed")
        raise HTTPException(status_code=400, detail="\u8bfb\u53d6\u8868\u5b57\u6bb5\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("list relation table columns failed")
        raise HTTPException(status_code=400, detail="\u8bfb\u53d6\u8868\u5b57\u6bb5\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5") from exc
