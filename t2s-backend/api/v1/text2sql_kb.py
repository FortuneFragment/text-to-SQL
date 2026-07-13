from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.domain_errors import (
    KnowledgeBaseNotFoundError,
    InvalidKnowledgeUsageError,
    KnowledgeUsageImmutableError,
    DataDictionaryDisabledError,
)
from schemas.knowledge import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
)
from services.common.knowledge_service import knowledge_service

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
            detail="读取知识库列表失败，请稍后重试",
        ) from exc


@router.post("", response_model=KnowledgeBaseResponse)
def create_knowledge_base(payload: KnowledgeBaseCreateRequest, db: Session = Depends(get_db)):
    try:
        return knowledge_service.create_kb(db, payload)
    except DataDictionaryDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (InvalidKnowledgeUsageError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("create knowledge base failed")
        raise HTTPException(
            status_code=400,
            detail="创建知识库失败，请稍后重试",
        ) from exc


@router.patch("/{kb_id}",response_model=KnowledgeBaseResponse,)
def update_knowledge_base(
    kb_id: int,
    payload: KnowledgeBaseUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        return knowledge_service.update_kb(
            db,
            kb_id,
            payload,
        )
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
    except KnowledgeUsageImmutableError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("update knowledge base failed")
        raise HTTPException(
            status_code=400,
            detail="更新知识库失败，请稍后重试",
        ) from exc


@router.delete("/{kb_id}")
def delete_knowledge_base(kb_id: int, db: Session = Depends(get_db)):
    try:
        knowledge_service.delete_kb(db, kb_id)
        return {"ok": True}
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete knowledge base failed")
        raise HTTPException(
            status_code=400,
            detail="删除知识库失败，请稍后重试",
        ) from exc
