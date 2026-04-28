from __future__ import annotations

import logging

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
logger = logging.getLogger(__name__)


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
        logger.exception("batch upload validation failed")
        raise HTTPException(
            status_code=400,
            detail="\u6587\u4ef6\u4e0a\u4f20\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u6587\u4ef6\u6216\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("batch upload failed")
        raise HTTPException(
            status_code=400,
            detail="\u6587\u4ef6\u4e0a\u4f20\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u6587\u4ef6\u6216\u7a0d\u540e\u91cd\u8bd5",
        ) from exc


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
        logger.exception("list files by kb validation failed")
        raise HTTPException(
            status_code=400,
            detail="\u67e5\u8be2\u6587\u4ef6\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("list files by kb failed")
        raise HTTPException(
            status_code=400,
            detail="\u67e5\u8be2\u6587\u4ef6\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc

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
        logger.exception("update file strategy validation failed")
        raise HTTPException(
            status_code=400,
            detail="\u66f4\u65b0\u6587\u4ef6\u5207\u7247\u7b56\u7565\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("update file strategy failed")
        raise HTTPException(
            status_code=400,
            detail="\u66f4\u65b0\u6587\u4ef6\u5207\u7247\u7b56\u7565\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc


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
        logger.exception("reprocess file validation failed")
        raise HTTPException(
            status_code=400,
            detail="\u91cd\u65b0\u5904\u7406\u6587\u4ef6\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("reprocess file failed")
        raise HTTPException(
            status_code=400,
            detail="\u91cd\u65b0\u5904\u7406\u6587\u4ef6\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc


@router.delete("/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    try:
        knowledge_file_service.delete_file(db=db, file_id=file_id)
        return {"ok": True}
    except ValueError as exc:
        logger.exception("delete file validation failed")
        raise HTTPException(
            status_code=400,
            detail="\u5220\u9664\u6587\u4ef6\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete file failed")
        raise HTTPException(
            status_code=400,
            detail="\u5220\u9664\u6587\u4ef6\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
        ) from exc
