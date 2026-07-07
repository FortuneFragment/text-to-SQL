from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.text2sql import CodeDictImportResponse
from services.text2sql import code_dict_import_service

router = APIRouter(prefix="/code-dict", tags=["text2sql-code-dict"])
logger = logging.getLogger(__name__)


async def _read_uploads(files: list[UploadFile]) -> list[dict]:
    return [{"filename": item.filename or "", "content": await item.read()} for item in files]


def _raise_import_error(exc: Exception, *, detail: str) -> None:
    raise HTTPException(status_code=400, detail=detail) from exc


@router.post("/import", response_model=CodeDictImportResponse)
async def import_code_dict(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """上传码值字典与字段绑定 Excel，落成两张最小结构码值表。"""
    payload = await _read_uploads(files)
    try:
        summary = code_dict_import_service.import_files(db, files=payload)
        return CodeDictImportResponse(**summary)
    except ValueError as exc:
        db.rollback()
        logger.warning("code dict import rejected: %s", exc)
        raise HTTPException(status_code=400, detail="码值字典导入失败，请检查文件格式后重试") from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("code dict import failed")
        _raise_import_error(exc, detail="码值字典导入失败，请检查文件格式后重试")


@router.post("/import/value", response_model=CodeDictImportResponse)
async def import_code_dict_value(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """只上传码值字典 Excel，不影响字段绑定。"""
    payload = await _read_uploads(files)
    try:
        summary = code_dict_import_service.import_value_files(db, files=payload)
        return CodeDictImportResponse(**summary)
    except ValueError as exc:
        db.rollback()
        logger.warning("code dict value import rejected: %s", exc)
        _raise_import_error(exc, detail="码值字典导入失败，请检查文件格式后重试")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("code dict value import failed")
        _raise_import_error(exc, detail="码值字典导入失败，请检查文件格式后重试")


@router.post("/import/binding", response_model=CodeDictImportResponse)
async def import_code_dict_binding(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """只上传字段码值绑定 Excel，不影响码值字典。"""
    payload = await _read_uploads(files)
    try:
        summary = code_dict_import_service.import_binding_files(db, files=payload)
        return CodeDictImportResponse(**summary)
    except ValueError as exc:
        db.rollback()
        logger.warning("code dict binding import rejected: %s", exc)
        _raise_import_error(exc, detail="字段绑定导入失败，请检查文件格式后重试")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("code dict binding import failed")
        _raise_import_error(exc, detail="字段绑定导入失败，请检查文件格式后重试")
