from __future__ import annotations

import io
import logging
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.text2sql import (
    CreateText2SQLRelationRequest,
    Text2SQLRelationBatchImportResponse,
    Text2SQLRelationItem,
    Text2SQLRelationListResponse,
    Text2SQLRelationTableColumnsResponse,
    UpdateText2SQLRelationRequest,
)
from services.text2sql import relation_service

router = APIRouter(prefix="/relation", tags=["text2sql-relation"])
logger = logging.getLogger(__name__)


@router.post("/import", response_model=Text2SQLRelationBatchImportResponse)
async def import_relations(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        return relation_service.import_relations_from_xlsx(
            db,
            filename=file.filename or "",
            content=content,
        )
    except ValueError as exc:
        logger.exception("import relations validation failed")
        raise HTTPException(status_code=400, detail="Import failed, please check the XLSX file") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("import relations failed")
        raise HTTPException(status_code=400, detail="Import failed, please check the XLSX file") from exc


@router.get("/export")
def export_relations(db: Session = Depends(get_db)):
    try:
        content = relation_service.export_relations_xlsx(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("export relations failed")
        raise HTTPException(status_code=400, detail="Export failed") from exc
    filename = f"relations-{datetime.now().strftime('%Y%m%d')}.xlsx"
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
    }
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("", response_model=Text2SQLRelationListResponse)
def list_relations(
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    table_name: str = "",
    db: Session = Depends(get_db),
):
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
        raise HTTPException(status_code=400, detail="Get relation list failed") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("list relations failed")
        raise HTTPException(status_code=400, detail="Get relation list failed") from exc


@router.post("", response_model=Text2SQLRelationItem)
def create_relation(payload: CreateText2SQLRelationRequest, db: Session = Depends(get_db)):
    try:
        return relation_service.create_relation(db, payload)
    except ValueError as exc:
        logger.exception("create relation validation failed")
        raise HTTPException(status_code=400, detail="Create relation failed") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("create relation failed")
        raise HTTPException(status_code=400, detail="Create relation failed") from exc


@router.put("/{relation_id}", response_model=Text2SQLRelationItem)
def update_relation(
    relation_id: int,
    payload: UpdateText2SQLRelationRequest,
    db: Session = Depends(get_db),
):
    try:
        return relation_service.update_relation(db, relation_id, payload)
    except ValueError as exc:
        logger.exception("update relation validation failed")
        raise HTTPException(status_code=400, detail="Update relation failed") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("update relation failed")
        raise HTTPException(status_code=400, detail="Update relation failed") from exc


@router.delete("/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(relation_id: int, db: Session = Depends(get_db)):
    try:
        relation_service.delete_relation(db, relation_id)
    except ValueError as exc:
        logger.exception("delete relation validation failed")
        raise HTTPException(status_code=400, detail="Delete relation failed") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete relation failed")
        raise HTTPException(status_code=400, detail="Delete relation failed") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/table/{table_name}/columns", response_model=Text2SQLRelationTableColumnsResponse)
def list_table_columns(table_name: str, db: Session = Depends(get_db)):
    try:
        return relation_service.get_table_columns(db, table_name)
    except ValueError as exc:
        logger.exception("list relation table columns validation failed")
        raise HTTPException(status_code=400, detail="Read table columns failed") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("list relation table columns failed")
        raise HTTPException(status_code=400, detail="Read table columns failed") from exc
