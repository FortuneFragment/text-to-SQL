from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from core.domain_errors import (
    InvalidKnowledgeUsageError,
    KnowledgeBaseNotFoundError,
    KnowledgeUsageMismatchError,
    KnowledgeOperationForbiddenError,
    FileProcessorMismatchError,
    FileUsageSnapshotMismatchError,
)
from schemas.knowledge import (
    ChunkPageResponse,
    ChunkResponse,
    FileBatchUploadItem,
    FilePageResponse,
    FileStrategyUpdateRequest,
    FileTaskSubmitResponse,
    KnowledgeFileResponse,
)
from services.common.knowledge_file_service import knowledge_file_service

router = APIRouter(prefix="/file", tags=["text2sql-file"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=list[FileBatchUploadItem])
async def upload_files(
    kb_id: int = Form(..., ge=1),
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
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except KnowledgeOperationForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (KnowledgeUsageMismatchError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("batch upload failed")
        raise HTTPException(
            status_code=400,
            detail="文件上传失败，请检查文件或稍后重试",
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
        rows, total, chunk_counts = (
            knowledge_file_service.list_files(
                db=db,
                kb_id=kb_id,
                page=safe_page,
                page_size=safe_page_size,
            )
        )
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except KnowledgeOperationForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (KnowledgeUsageMismatchError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("list files by kb failed")
        raise HTTPException(
            status_code=400,
            detail="查询文件列表失败，请稍后重试",
        ) from exc
    items: list[KnowledgeFileResponse] = []

    for row in rows:
        model = KnowledgeFileResponse.model_validate(
            row
        )
        model.chunk_count = chunk_counts.get(
            int(row.id),
            0,
        )
        items.append(model)

    return FilePageResponse(
        items=items,
        total=int(total),
        page=safe_page,
        page_size=safe_page_size,
        total_pages=knowledge_file_service.build_total_pages(int(total), safe_page_size),
    )


@router.get(
    "/{file_id}",
    response_model=KnowledgeFileResponse,
)
def get_file(
    file_id: int,
    db: Session = Depends(get_db),
):
    try:
        file_entity, chunk_count = (
            knowledge_file_service.get_file(
                db=db,
                file_id=file_id,
            )
        )

        model = KnowledgeFileResponse.model_validate(
            file_entity
        )
        model.chunk_count = int(chunk_count)

        return model

    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
    except KnowledgeOperationForbiddenError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )
    except (
        InvalidKnowledgeUsageError,
        KnowledgeUsageMismatchError,
        FileProcessorMismatchError,
        FileUsageSnapshotMismatchError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/{file_id}/chunks", response_model=ChunkPageResponse)
def list_file_chunks(
    file_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size), 100))
    try:
        rows, total = (
            knowledge_file_service.list_file_chunks(
                db=db,
                file_id=file_id,
                page=safe_page,
                page_size=safe_page_size,
            )
        )
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
    except KnowledgeOperationForbiddenError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )
    except (
            InvalidKnowledgeUsageError,
            KnowledgeUsageMismatchError,
            FileProcessorMismatchError,
            FileUsageSnapshotMismatchError,
            ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
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
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except KnowledgeOperationForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (KnowledgeUsageMismatchError, FileProcessorMismatchError, FileUsageSnapshotMismatchError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("update file strategy failed")
        raise HTTPException(
            status_code=400,
            detail="更新文件切片策略失败，请稍后重试",
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
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except KnowledgeOperationForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (KnowledgeUsageMismatchError, FileProcessorMismatchError, FileUsageSnapshotMismatchError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("reprocess file failed")
        raise HTTPException(
            status_code=400,
            detail="重新处理文件失败，请稍后重试",
        ) from exc


@router.delete("/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    try:
        knowledge_file_service.delete_file(db=db, file_id=file_id)
        return {"ok": True}
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except KnowledgeOperationForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (KnowledgeUsageMismatchError, FileProcessorMismatchError, FileUsageSnapshotMismatchError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete file failed")
        raise HTTPException(
            status_code=400,
            detail="删除文件失败，请稍后重试",
        ) from exc
