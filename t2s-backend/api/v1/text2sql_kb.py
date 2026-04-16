from __future__ import annotations

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


@router.get("", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(db: Session = Depends(get_db)):
    return knowledge_service.list_kbs(db)


@router.post("", response_model=KnowledgeBaseResponse)
def create_knowledge_base(payload: KnowledgeBaseCreateRequest, db: Session = Depends(get_db)):
    try:
        return knowledge_service.create_kb(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(kb_id: int, payload: KnowledgeBaseUpdateRequest, db: Session = Depends(get_db)):
    try:
        return knowledge_service.update_kb(db, kb_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{kb_id}")
def delete_knowledge_base(kb_id: int, db: Session = Depends(get_db)):
    try:
        knowledge_service.delete_kb(db, kb_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
