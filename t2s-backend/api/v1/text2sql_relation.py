from fastapi import APIRouter, Depends, HTTPException, Response, status
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"获取关系列表失败: {exc}") from exc


@router.post("", response_model=Text2SQLRelationItem)
def create_relation(payload: CreateText2SQLRelationRequest, db: Session = Depends(get_db)):
    """创建一条表关联关系。"""
    try:
        return relation_service.create_relation(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"创建关系失败: {exc}") from exc


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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"更新关系失败: {exc}") from exc


@router.delete("/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(relation_id: int, db: Session = Depends(get_db)):
    """删除一条关系配置。"""
    try:
        relation_service.delete_relation(db, relation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"删除关系失败: {exc}") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/table/{table_name}/columns", response_model=Text2SQLRelationTableColumnsResponse)
def list_table_columns(table_name: str, db: Session = Depends(get_db)):
    """读取关系配置页需要的表字段列表。"""
    try:
        return relation_service.get_table_columns(db, table_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"读取表字段失败: {exc}") from exc
