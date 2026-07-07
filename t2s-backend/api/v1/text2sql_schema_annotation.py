from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.text2sql import SchemaAnnotationImportResponse
from services.text2sql import schema_annotation_import_service

router = APIRouter(prefix="/schema-annotation", tags=["text2sql-schema-annotation"])
logger = logging.getLogger(__name__)


@router.post("/import", response_model=SchemaAnnotationImportResponse)
async def import_schema_annotations(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    try:
        summary = schema_annotation_import_service.import_file(
            db,
            filename=file.filename or "",
            content=content,
        )
        return SchemaAnnotationImportResponse(**summary)
    except ValueError as exc:
        db.rollback()
        logger.warning("schema annotation import rejected: %s", exc)
        raise HTTPException(status_code=400, detail="字段注释导入失败，请检查文件格式后重试") from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("schema annotation import failed")
        raise HTTPException(status_code=400, detail="字段注释导入失败，请检查文件格式后重试") from exc
