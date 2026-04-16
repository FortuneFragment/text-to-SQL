from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from repositories.knowledge_file_repo import KnowledgeFileRepository
from schemas.knowledge import (
    ChunkPageResponse,
    ChunkResponse,
    FileBatchUploadItem,
    FilePageResponse,
    FileStrategyUpdateRequest,
    FileTaskSubmitResponse,
    KnowledgeFileResponse,
)
from services.knowledge_file_service import knowledge_file_service

router = APIRouter(prefix="/file", tags=["text2sql-file"])


@router.post("/upload", response_model=list[FileBatchUploadItem])
async def upload_files(
    kb_id: int | None = Form(default=None),
    files: list[UploadFile] = File(...),
    custom_chunk_size: int | None = Form(default=None),
    custom_chunk_overlap: int | None = Form(default=None),
    db: Session = Depends(get_db),
):
    try:
        return await knowledge_file_service.batch_upload(
            db=db,
            kb_id=kb_id,
            files=files,
            custom_chunk_size=custom_chunk_size,
            custom_chunk_overlap=custom_chunk_overlap,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/kb/{kb_id}", response_model=FilePageResponse)
def list_files_by_kb(
    kb_id: int,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size), 100))

    try:
        rows, total = knowledge_file_service.list_files(
            db=db,
            kb_id=kb_id,
            page=safe_page,
            page_size=safe_page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo = KnowledgeFileRepository(db)
    items: list[KnowledgeFileResponse] = []
    for row in rows:
        model = KnowledgeFileResponse.model_validate(row)
        model.chunk_count = repo.count_chunks_by_file_id(int(row.id))
        items.append(model)

    return FilePageResponse(
        items=items,
        total=int(total),
        page=safe_page,
        page_size=safe_page_size,
        total_pages=knowledge_file_service.build_total_pages(int(total), safe_page_size),
    )


@router.get("/{file_id}", response_model=KnowledgeFileResponse)
def get_file(file_id: int, db: Session = Depends(get_db)):
    repo = KnowledgeFileRepository(db)
    file_entity = repo.get_by_id(file_id)
    if file_entity is None:
        raise HTTPException(status_code=404, detail="File not found")

    model = KnowledgeFileResponse.model_validate(file_entity)
    model.chunk_count = repo.count_chunks_by_file_id(file_id)
    return model


@router.get("/{file_id}/chunks", response_model=ChunkPageResponse)
def list_file_chunks(
    file_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size), 100))

    repo = KnowledgeFileRepository(db)
    file_entity = repo.get_by_id(file_id)
    if file_entity is None:
        raise HTTPException(status_code=404, detail="File not found")

    rows, total = repo.list_chunks_by_file_paginated(file_id=file_id, page=safe_page, page_size=safe_page_size)
    return ChunkPageResponse(
        items=[ChunkResponse.model_validate(row) for row in rows],
        total=int(total),
        page=safe_page,
        page_size=safe_page_size,
        total_pages=knowledge_file_service.build_total_pages(int(total), safe_page_size),
    )


@router.put("/{file_id}/strategy", response_model=FileTaskSubmitResponse)
def update_file_strategy(
    file_id: int,
    payload: FileStrategyUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        _, task_id = knowledge_file_service.update_strategy_and_reprocess(
            db=db,
            file_id=file_id,
            custom_chunk_size=int(payload.custom_chunk_size),
            custom_chunk_overlap=int(payload.custom_chunk_overlap),
        )
        return FileTaskSubmitResponse(
            file_id=file_id,
            task_id=task_id,
            status="queued",
            message="File strategy updated, reprocess task queued",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{file_id}/reprocess", response_model=FileTaskSubmitResponse)
def reprocess_file(file_id: int, db: Session = Depends(get_db)):
    try:
        task_id = knowledge_file_service.reprocess_file(db=db, file_id=file_id)
        return FileTaskSubmitResponse(
            file_id=file_id,
            task_id=task_id,
            status="queued",
            message="Reprocess task queued",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    try:
        knowledge_file_service.delete_file(db=db, file_id=file_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
