from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.knowledge import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
)
from services.knowledge_service import knowledge_service

router = APIRouter(prefix="/kb", tags=["text2sql-kb"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(db: Session = Depends(get_db)):
    try:
        return knowledge_service.list_kbs(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("list knowledge bases failed")
        raise HTTPException(
            status_code=400,
            detail="\u8bfb\u53d6\u77e5\u8bc6\u5e93\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc


@router.post("", response_model=KnowledgeBaseResponse)
def create_knowledge_base(payload: KnowledgeBaseCreateRequest, db: Session = Depends(get_db)):
    try:
        return knowledge_service.create_kb(db, payload)
    except ValueError as exc:
        logger.exception("create knowledge base validation failed")
        raise HTTPException(
            status_code=400,
            detail="\u521b\u5efa\u77e5\u8bc6\u5e93\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("create knowledge base failed")
        raise HTTPException(
            status_code=400,
            detail="\u521b\u5efa\u77e5\u8bc6\u5e93\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(kb_id: int, payload: KnowledgeBaseUpdateRequest, db: Session = Depends(get_db)):
    try:
        return knowledge_service.update_kb(db, kb_id, payload)
    except ValueError as exc:
        logger.exception("update knowledge base validation failed")
        raise HTTPException(
            status_code=400,
            detail="\u66f4\u65b0\u77e5\u8bc6\u5e93\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("update knowledge base failed")
        raise HTTPException(
            status_code=400,
            detail="\u66f4\u65b0\u77e5\u8bc6\u5e93\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc


@router.delete("/{kb_id}")
def delete_knowledge_base(kb_id: int, db: Session = Depends(get_db)):
    try:
        knowledge_service.delete_kb(db, kb_id)
        return {"ok": True}
    except ValueError as exc:
        logger.exception("delete knowledge base validation failed")
        raise HTTPException(
            status_code=400,
            detail="\u5220\u9664\u77e5\u8bc6\u5e93\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete knowledge base failed")
        raise HTTPException(
            status_code=400,
            detail="\u5220\u9664\u77e5\u8bc6\u5e93\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
