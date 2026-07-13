from __future__ import annotations

import json
import logging
from collections.abc import Generator
from queue import Queue
from threading import Thread
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from core.database import SessionLocal, get_db
from repositories.minio_repo import minio_repo
from schemas.document_qa import (
    DocumentQARequest,
    DocumentQAResponse,
    TableArtifactDetailResponse,
    TableJobListResponse,
    TableJobResponse,
    TableListResponse,
    TableIndexDocumentResponse,
    TableQARequest,
    TableQAResponse,
    TableSearchRequest,
    TableSearchResponse,
    TableSearchHit,
    TableSemanticArtifactResponse,
    TableSourceResponse,
    TableTreeResponse,
    TableUploadResponse,
)
from services.document_qa import document_qa_service, table_qa_service, table_semantic_service
from tasks.celery_app import celery_app
from schemas.task import TaskSubmitResponse

from core.domain_errors import (
    FileProcessorMismatchError,
    FileUsageSnapshotMismatchError,
    KnowledgeBaseNotFoundError,
    KnowledgeOperationForbiddenError,
    KnowledgeUsageMismatchError,
    TableArtifactContextMismatchError,
    TableArtifactNotFoundError,
)

from core.auth import get_current_user, require_info_admin

router = APIRouter(
    prefix="/document-qa",
    tags=["document-qa"],
    dependencies=[Depends(get_current_user)],
)

admin_router = APIRouter(
    prefix="/document-qa",
    tags=["document-qa-admin"],
    dependencies=[Depends(require_info_admin)],
)

compat_router = APIRouter(tags=["table-qa-compat"])
logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/query", response_model=DocumentQAResponse)
def query_document_qa(payload: DocumentQARequest, db: Session = Depends(get_db)):
    from core.domain_errors import (
        InvalidKnowledgeUsageError,
        KnowledgeBaseNotFoundError,
        KnowledgeUsageMismatchError,
        KnowledgeOperationForbiddenError,
    )
    try:
        result = document_qa_service.query(
            db,
            question=payload.question,
            kb_id=payload.kb_id,
            history=[item.model_dump() for item in payload.history],
            top_k=payload.top_k,
        )
        return DocumentQAResponse(**result)
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
            ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    except RuntimeError as exc:
        logger.exception("document QA LLM failed")
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@router.post("/query/stream")
def query_document_qa_stream(payload: DocumentQARequest):
    from core.domain_errors import (
        InvalidKnowledgeUsageError,
        KnowledgeBaseNotFoundError,
        KnowledgeUsageMismatchError,
        KnowledgeOperationForbiddenError,
    )
    def event_stream() -> Generator[str, None, None]:
        queue: Queue[tuple[str, dict] | None] = Queue()

        def emit(event: str, data: dict) -> None:
            queue.put((event, data))

        def worker() -> None:
            db = SessionLocal()

            try:
                emit(
                    "status",
                    {
                        "step": "retrieving",
                        "message": (
                            "正在检索文档与表格知识库..."
                        ),
                    },
                )

                result = document_qa_service.query(
                    db,
                    question=payload.question,
                    kb_id=payload.kb_id,
                    history=[
                        item.model_dump()
                        for item in payload.history
                    ],
                    top_k=payload.top_k,
                )

                emit(
                    "status",
                    {
                        "step": "completed",
                        "message": "问答完成",
                    },
                )

                emit(
                    "done",
                    DocumentQAResponse(
                        **result
                    ).model_dump(),
                )

            except KnowledgeBaseNotFoundError as exc:
                emit(
                    "error",
                    {
                        "code": exc.code,
                        "message": str(exc),
                    },
                )

            except KnowledgeOperationForbiddenError as exc:
                emit(
                    "error",
                    {
                        "code": exc.code,
                        "message": str(exc),
                    },
                )

            except (
                InvalidKnowledgeUsageError,
                KnowledgeUsageMismatchError,
                ValueError,
            ) as exc:
                emit(
                    "error",
                    {
                        "code": getattr(
                            exc,
                            "code",
                            "INVALID_REQUEST",
                        ),
                        "message": str(exc),
                    },
                )

            except RuntimeError as exc:
                logger.exception(
                    "stream document QA LLM failed"
                )

                emit(
                    "error",
                    {
                        "code": "LLM_SERVICE_ERROR",
                        "message": str(exc),
                    },
                )

            except Exception:
                logger.exception(
                    "stream document QA failed"
                )

                emit(
                    "error",
                    {
                        "code": "INTERNAL_ERROR",
                        "message": (
                            "问答执行失败，请稍后重试"
                        ),
                    },
                )

            finally:
                db.close()

                # 无论成功还是失败，都必须通知生成器结束。
                queue.put(None)

        Thread(target=worker, daemon=True).start()
        while True:
            item = queue.get()
            if item is None:
                break
            event, data = item
            yield _sse(event, data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@admin_router.post("/table/upload", response_model=TableUploadResponse)
async def upload_table(
    file: UploadFile = File(...),
    kb_id: int = Form(..., ge=1),
    sheet_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    try:
        return TableUploadResponse(
            **await table_semantic_service.upload_table(
                db=db,
                file=file,
                kb_id=kb_id,
                sheet_name=sheet_name,
            )
        )
    except ValueError as exc:
        logger.exception("table upload validation failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("table upload failed")
        raise HTTPException(status_code=400, detail="表格上传失败，请稍后重试") from exc


@admin_router.get("/table/tables", response_model=TableListResponse)
def list_tables(
    kb_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    rows = table_semantic_service.list_tables(db, kb_id=kb_id, limit=limit)
    return TableListResponse(
        items=[TableSemanticArtifactResponse(**table_semantic_service.artifact_to_response(row)) for row in rows]
    )


@admin_router.post("/table/search", response_model=TableSearchResponse)
def search_tables(payload: TableSearchRequest, db: Session = Depends(get_db)):
    rows = table_semantic_service.search_tables(
        db,
        question=payload.question,
        kb_id=payload.kb_id,
        top_k=payload.top_k,
    )
    return TableSearchResponse(items=[TableSearchHit(**_normalize_table_search_hit(row)) for row in rows])


@admin_router.get(
    "/table/jobs",
    response_model=TableJobListResponse,
)
def list_table_jobs(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    rows = table_semantic_service.list_jobs(
        db,
        limit=limit,
    )

    return TableJobListResponse(
        items=[
            TableJobResponse(
                **_merge_table_job_runtime(
                    row
                )
            )
            for row in rows
        ]
    )


@admin_router.get(
    "/table/jobs/by-table/{table_id}",
    response_model=TableJobResponse,
)
def get_table_job_by_table_id(
    table_id: str,
    db: Session = Depends(get_db),
):
    try:
        row = (
            table_semantic_service
            .get_job_by_table_id(
                db,
                table_id,
            )
        )

        return TableJobResponse(
            **_merge_table_job_runtime(
                row
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="表格不存在",
        ) from exc


@admin_router.get(
    "/table/jobs/{task_id}",
    response_model=TableJobResponse,
)
def get_table_job(
    task_id: str,
    db: Session = Depends(get_db),
):
    try:
        database_row = (
            table_semantic_service
            .get_job_by_task_id(
                db,
                task_id,
            )
        )
    except ValueError:
        # 兼容尚未写入数据库或非本模块任务。
        database_row = {
            "task_id": str(task_id),
            "state": "PENDING",
            "ready": False,
            "successful": False,
            "table_ids": [],
            "sheet_names": [],
            "total_sheets": 0,
            "completed_sheets": 0,
            "progress": 0.0,
            "tables": [],
        }

    merged = _merge_table_job_runtime(
        database_row
    )

    return TableJobResponse(**merged)


@admin_router.post("/table/answer", response_model=TableQAResponse)
def answer_table(payload: TableQARequest, db: Session = Depends(get_db)):
    try:
        if payload.tree:
            result = table_qa_service.answer_tree(
                db,
                question=payload.question,
                tree=payload.tree,
                metadata=payload.metadata,
                history=[item.model_dump() for item in payload.history],
                top_k=payload.limit or payload.top_k,
                use_llm=payload.use_llm,
            )
        elif payload.table_id:
            result = table_qa_service.answer(
                db,
                table_id=payload.table_id,
                question=payload.question,
                history=[item.model_dump() for item in payload.history],
                top_k=payload.top_k,
            )
        else:
            result = table_qa_service.answer_global(
                db,
                question=payload.question,
                kb_id=payload.kb_id,
                history=[item.model_dump() for item in payload.history],
                top_k=payload.top_k,
            )
        return TableQAResponse(**result)
    except RuntimeError as exc:
        logger.exception("table QA LLM failed")
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("table QA answer failed")
        raise HTTPException(status_code=400, detail="表格问答失败，请稍后重试") from exc


@admin_router.get("/table/tables/{table_id}", response_model=TableSemanticArtifactResponse)
def get_table(table_id: str, db: Session = Depends(get_db)):
    try:
        row = table_semantic_service.get_table(db, table_id)
        return TableSemanticArtifactResponse(**table_semantic_service.artifact_to_response(row))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="表格不存在") from exc


@admin_router.get("/table/tables/{table_id}/artifact", response_model=TableArtifactDetailResponse)
def get_table_artifact(table_id: str, db: Session = Depends(get_db)):
    try:
        return TableArtifactDetailResponse(**table_semantic_service.get_table_artifact(db, table_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="表格不存在") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get table artifact failed")
        raise HTTPException(status_code=400, detail="读取表格解析产物失败") from exc


@admin_router.get("/table/tables/{table_id}/index-document", response_model=TableIndexDocumentResponse)
def get_table_index_document(table_id: str, db: Session = Depends(get_db)):
    try:
        return TableIndexDocumentResponse(document=table_semantic_service.get_table_index_document(db, table_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="表格不存在") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get table index document failed")
        raise HTTPException(status_code=400, detail="读取表级索引文档失败") from exc


@admin_router.get("/table/tables/{table_id}/source", response_model=TableSourceResponse)
def get_table_source(table_id: str, db: Session = Depends(get_db)):
    try:
        return TableSourceResponse(**table_semantic_service.get_table_source_url(db, table_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="表格源文件不存在") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get table source failed")
        raise HTTPException(status_code=400, detail="读取表格源文件失败") from exc


@admin_router.get("/table/tables/{table_id}/normalized", response_model=TableSourceResponse)
def get_table_normalized(table_id: str, db: Session = Depends(get_db)):
    try:
        return TableSourceResponse(**table_semantic_service.get_table_normalized_url(db, table_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="标准化文件不存在") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get table normalized failed")
        raise HTTPException(status_code=400, detail="读取标准化文件失败") from exc


@admin_router.get("/table/tables/{table_id}/tree", response_model=TableTreeResponse)
def get_table_tree(table_id: str, db: Session = Depends(get_db)):
    try:
        payload = table_semantic_service.get_table_tree(db, table_id)
        return TableTreeResponse(
            table_id=table_id,
            tree=payload.get("tree") or {},
            tree_with_cell_refs=payload.get("tree_with_cell_refs") or {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="表格不存在") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get table tree failed")
        raise HTTPException(status_code=400, detail="读取表格语义树失败") from exc


def _normalize_table_search_hit(row: dict) -> dict:
    return {
        "kb_id": row.get("kb_id"),
        "file_id": row.get("file_id"),
        "table_id": str(row.get("table_id") or ""),
        "table_title": str(row.get("table_title") or ""),
        "file_name": str(row.get("file_name") or ""),
        "sheet_name": str(row.get("sheet_name") or ""),
        "summary_text": str(row.get("summary_text") or ""),
        "candidate_fields": row.get("candidate_fields") if isinstance(row.get("candidate_fields"), list) else [],
        "tree_metric_names": row.get("tree_metric_names") if isinstance(row.get("tree_metric_names"), list) else [],
        "tree_path_text": row.get("tree_path_text") if isinstance(row.get("tree_path_text"), list) else [],
        "tree_leaf_text": row.get("tree_leaf_text") if isinstance(row.get("tree_leaf_text"), list) else [],
        "tree_search_text": str(row.get("tree_search_text") or ""),
        "tree_object_name": str(row.get("tree_object_name") or ""),
        "source_object_name": str(row.get("source_object_name") or ""),
        "normalized_object_name": str(row.get("normalized_object_name") or ""),
        "parse_mode": str(row.get("parse_mode") or ""),
        "large_table_reason": str(row.get("large_table_reason") or ""),
        "embedding_error": str(row.get("embedding_error") or ""),
        "row_count": int(row.get("row_count") or 0),
        "column_count": int(row.get("column_count") or 0),
        "score": float(row.get("score") or 0.0),
        "source": str(row.get("source") or ""),
    }


def _table_to_pipeline_summary(row: dict) -> dict:
    source_object = str(row.get("source_object_name") or row.get("source_object") or "")
    normalized_object = str(row.get("normalized_object_name") or row.get("xlsx_object") or "")
    tree_object = str(row.get("tree_object_name") or row.get("tree_object") or "")
    parse_plan = row.get("parse_plan") if isinstance(row.get("parse_plan"), dict) else {}
    parse_mode = str(row.get("parse_mode") or ("plan_based" if parse_plan else "heuristic"))
    return {
        "table_id": str(row.get("table_id") or ""),
        "batch_id": str(row.get("batch_id") or ""),
        "filename": str(row.get("file_name") or row.get("filename") or ""),
        "file_name": str(row.get("file_name") or row.get("filename") or ""),
        "normalized_filename": str(row.get("normalized_filename") or f"{row.get('table_title') or row.get('table_id')}.xlsx"),
        "source_extension": str(row.get("source_extension") or ""),
        "sheet_name": str(row.get("sheet_name") or ""),
        "table_title": str(row.get("table_title") or ""),
        "parse_mode": parse_mode,
        "large_table_reason": str(row.get("large_table_reason") or ""),
        "coverage": row.get("coverage") if isinstance(row.get("coverage"), dict) else {},
        "summary_text": str(row.get("summary_text") or ""),
        "candidate_fields": row.get("candidate_fields") if isinstance(row.get("candidate_fields"), list) else [],
        "tree_metric_names": row.get("tree_metric_names") if isinstance(row.get("tree_metric_names"), list) else [],
        "tree_path_text": row.get("tree_path_text") if isinstance(row.get("tree_path_text"), list) else [],
        "tree_leaf_text": row.get("tree_leaf_text") if isinstance(row.get("tree_leaf_text"), list) else [],
        "embedding_error": str(row.get("embedding_error") or ""),
        "indexed": row.get("source") != "artifact_fallback",
        "minio_objects": {
            "source_object": source_object,
            "xlsx_object": normalized_object,
            "tree_object": tree_object,
        },
        "source_object": source_object,
        "xlsx_object": normalized_object,
        "tree_object": tree_object,
        "row_count": int(row.get("row_count") or 0),
        "column_count": int(row.get("column_count") or 0),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _artifact_to_pipeline_payload(artifact: dict) -> dict:
    parse_plan = artifact.get("parse_plan") if isinstance(artifact.get("parse_plan"), dict) else {}
    return {
        **artifact,
        "filename": artifact.get("file_name", ""),
        "normalized_filename": f"{artifact.get('table_title') or artifact.get('table_id')}.xlsx",
        "parse_mode": str(artifact.get("parse_mode") or ("plan_based" if parse_plan else "heuristic")),
        "large_table_reason": str(artifact.get("large_table_reason") or ""),
        "final_json_tree": str(
            artifact.get("final_json_tree")
            or json.dumps(artifact.get("tree_with_cell_refs") or {}, ensure_ascii=False, default=str)
        ),
        "markdown_table": str(artifact.get("markdown_table") or ""),
        "normalized_headers": str(
            artifact.get("normalized_headers")
            or json.dumps(
                {
                    "hierarchy_columns": [],
                    "value_columns": artifact.get("candidate_fields", []),
                },
                ensure_ascii=False,
            )
        ),
        "hierarchy_definition": str(
            artifact.get("hierarchy_definition") or json.dumps(parse_plan, ensure_ascii=False, default=str)
        ),
        "minio_objects": {
            "source_object": artifact.get("source_object_name", ""),
            "xlsx_object": artifact.get("normalized_object_name", ""),
            "tree_object": artifact.get("tree_object_name", ""),
        },
    }


_TABLE_JOB_RUNTIME_FIELDS = (
    "file_id",
    "batch_id",
    "table_ids",
    "sheet_names",
    "total_sheets",
    "completed_sheets",
    "progress",
    "current_table_id",
    "current_sheet_name",
    "completed_table_ids",
)


def _merge_table_job_runtime(
    row: dict,
) -> dict:
    merged = dict(row)

    task_id = str(
        merged.get("task_id") or ""
    ).strip()

    if not task_id:
        return merged

    async_result = celery_app.AsyncResult(
        task_id
    )
    celery_state = str(
        async_result.state or "PENDING"
    )

    info = (
        async_result.info
        if isinstance(async_result.info, dict)
        else {}
    )

    final_result = (
        async_result.result
        if (
            celery_state == "SUCCESS"
            and isinstance(
                async_result.result,
                dict,
            )
        )
        else {}
    )

    runtime_payload = (
        final_result or info
    )

    # PENDING 也可能表示结果已过期。
    # 此时保留数据库中的完成/失败状态。
    if celery_state != "PENDING":
        merged["state"] = celery_state
        merged["ready"] = bool(
            async_result.ready()
        )
        merged["successful"] = bool(
            async_result.successful()
        )

    for field in _TABLE_JOB_RUNTIME_FIELDS:
        if field in runtime_payload:
            merged[field] = runtime_payload[
                field
            ]

    if final_result:
        merged["result"] = final_result

        # `result.tables` 是 Celery 处理摘要，不是完整的语义树产物。
        # `TableJobResponse.tables` 必须保留数据库返回的 artifact 数据，
        # 否则会因缺少 id、usage_snapshot 等字段触发响应校验错误。

    if celery_state == "FAILURE":
        merged["state"] = "FAILURE"
        merged["ready"] = True
        merged["successful"] = False
        merged["error"] = str(
            async_result.result
        )

    return merged


def _job_to_pipeline_payload(
    row: dict,
) -> dict:
    state = str(row.get("state") or "")

    if (
        row.get("successful")
        or state.upper() == "SUCCESS"
        or state == "完成"
    ):
        status = "completed"
    elif (
        state.upper() in {"FAILURE", "REVOKED"}
        or state == "失败"
    ):
        status = "failed"
    elif (
        state.upper()
        in {"STARTED", "PROGRESS", "RETRY"}
        or state == "处理中"
    ):
        status = "running"
    else:
        status = "queued"

    task_id = str(
        row.get("task_id") or ""
    ).strip()

    result = (
        row.get("result")
        if isinstance(row.get("result"), dict)
        else {}
    )

    row_table_ids = (
        row.get("table_ids")
        if isinstance(row.get("table_ids"), list)
        else []
    )
    result_table_ids = (
        result.get("table_ids")
        if isinstance(result.get("table_ids"), list)
        else []
    )

    table_ids = [
        str(item)
        for item in (
            row_table_ids or result_table_ids
        )
        if item
    ]

    row_tables = (
        row.get("tables")
        if isinstance(row.get("tables"), list)
        else []
    )
    result_tables = (
        result.get("tables")
        if isinstance(result.get("tables"), list)
        else []
    )

    tables = row_tables or result_tables

    table_id = str(
        row.get("table_id") or ""
    ).strip()

    if not table_id and table_ids:
        table_id = table_ids[0]

    batch_id = str(
        row.get("batch_id")
        or result.get("batch_id")
        or ""
    ).strip()

    row_sheet_names = (
        row.get("sheet_names")
        if isinstance(
            row.get("sheet_names"),
            list,
        )
        else []
    )

    result_sheet_names = (
        result.get("sheet_names")
        if isinstance(
            result.get("sheet_names"),
            list,
        )
        else []
    )

    sheet_names = [
        str(item)
        for item in (
            row_sheet_names
            or result_sheet_names
            or [
                table.get("sheet_name")
                for table in tables
                if isinstance(table, dict)
            ]
        )
        if item is not None
    ]

    raw_total_sheets = row.get("total_sheets")
    if raw_total_sheets is None:
        raw_total_sheets = result.get(
            "total_sheets"
        )

    total_sheets = int(
        raw_total_sheets
        if raw_total_sheets is not None
        else (
            len(table_ids)
            or len(sheet_names)
        )
    )

    raw_completed_sheets = row.get(
        "completed_sheets"
    )
    if raw_completed_sheets is None:
        raw_completed_sheets = result.get(
            "completed_sheets"
        )

    completed_sheets = int(
        raw_completed_sheets
        if raw_completed_sheets is not None
        else len(tables)
    )

    progress = float(
        row.get("progress")
        if row.get("progress") is not None
        else result.get("progress")
        if result.get("progress") is not None
        else (
            completed_sheets / total_sheets
            if total_sheets
            else 0.0
        )
    )

    return {
        # 必须始终使用 Celery task_id。
        "job_id": task_id,
        "task_id": task_id,

        "batch_id": batch_id,
        "table_id": table_id,
        "table_ids": table_ids,

        "filename": str(
            row.get("file_name")
            or row.get("filename")
            or ""
        ),
        "file_name": str(
            row.get("file_name")
            or row.get("filename")
            or ""
        ),

        "sheet_name": row.get("sheet_name"),
        "sheet_names": sheet_names,

        "status": status,
        "celery_state": state,
        "state": state,

        "ready": bool(row.get("ready")),
        "successful": bool(
            row.get("successful")
        ),

        "total_sheets": total_sheets,
        "completed_sheets": completed_sheets,
        "progress": progress,

        "current_table_id": (
            row.get("current_table_id")
            or result.get("current_table_id")
        ),
        "current_sheet_name": (
            row.get("current_sheet_name")
            or result.get("current_sheet_name")
        ),

        "submitted_at": row.get("created_at"),
        "started_at": None,
        "finished_at": (
            row.get("updated_at")
            if status in {"completed", "failed"}
            else None
        ),

        "error": row.get("error"),
        "result": (
            result
            if result
            else row.get("result")
        ),
        "tables": tables,
        "queue_size": 0,
    }


def _download_table_file(*, table_id: str, kind: str, db: Session) -> Response:
    try:
        artifact = table_semantic_service.get_table_artifact(db, table_id)
        if kind == "source":
            object_name = str(artifact.get("source_object_name") or "").strip()
            filename = str(artifact.get("file_name") or f"{table_id}.xlsx")
            media_type = "application/octet-stream"
        else:
            object_name = str(artifact.get("normalized_object_name") or "").strip()
            filename = f"{artifact.get('table_title') or table_id}.xlsx"
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if not object_name:
            raise ValueError(f"{kind} object not found")
        content = minio_repo.get_file_bytes(object_name)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("download table file failed")
        raise HTTPException(status_code=502, detail=f"MinIO operation failed: {exc}") from exc


@compat_router.post(
    "/table-pipeline/upload",
    status_code=202,
)
async def compat_upload_table_to_pipeline(
    file: UploadFile = File(...),
    kb_id: int = Form(..., ge=1),
    sheet_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    result = await upload_table(
        file=file,
        kb_id=kb_id,
        sheet_name=sheet_name,
        db=db,
    )
    payload = result.model_dump()

    task_id = str(payload.get("task_id") or "").strip()
    batch_id = str(payload.get("batch_id") or "").strip()

    table_ids = [
        str(item)
        for item in (
            payload.get("table_ids")
            or (
                [payload.get("table_id")]
                if payload.get("table_id")
                else []
            )
        )
        if item
    ]

    sheet_names = [
        str(item)
        for item in (
            payload.get("sheet_names")
            or ([sheet_name] if sheet_name else [])
        )
        if item is not None
    ]

    if not task_id:
        raise HTTPException(
            status_code=500,
            detail="表格批任务创建成功，但未生成 task_id",
        )

    primary_table_id = (
        table_ids[0]
        if table_ids
        else ""
    )

    status = str(
        payload.get("status") or "queued"
    )

    # 一个文件只返回一个批任务 job。
    batch_job = {
        "job_id": task_id,
        "task_id": task_id,
        "batch_id": batch_id,

        # table_id 仅用于兼容旧调用方；
        # 完整列表以 table_ids 为准。
        "table_id": primary_table_id,
        "table_ids": table_ids,

        "filename": file.filename or "",
        "sheet_name": (
            sheet_names[0]
            if len(sheet_names) == 1
            else None
        ),
        "sheet_names": sheet_names,

        "status": status,
        "total_sheets": (
            len(sheet_names)
            or len(table_ids)
        ),
        "completed_sheets": 0,

        "result": None,
        "error": None,
        "queue_size": 0,
    }

    return {
        **payload,
        "task_id": task_id,
        "batch_id": batch_id,
        "filename": file.filename or "",
        "sheet_name": sheet_name,
        "sheet_names": sheet_names,
        "sheet_count": (
            len(sheet_names)
            or len(table_ids)
        ),
        "status": status,
        "jobs": [batch_job],
    }


@compat_router.get(
    "/table-pipeline/jobs"
)
def compat_list_pipeline_jobs(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    rows = table_semantic_service.list_jobs(
        db,
        limit=limit,
    )

    return {
        "jobs": [
            _job_to_pipeline_payload(
                _merge_table_job_runtime(
                    row
                )
            )
            for row in rows
        ]
    }


@compat_router.get(
    "/table-pipeline/jobs/by-table/{table_id}"
)
def compat_get_pipeline_job_by_table_id(
    table_id: str,
    db: Session = Depends(get_db),
):
    try:
        row = (
            table_semantic_service
            .get_job_by_table_id(
                db,
                table_id,
            )
        )

        payload = _job_to_pipeline_payload(
            _merge_table_job_runtime(
                row
            )
        )

        if not payload["task_id"]:
            raise ValueError(
                "对应文件没有有效的 task_id"
            )

        return payload

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Job not found for table: "
                f"{table_id}"
            ),
        ) from exc


@compat_router.get("/table-pipeline/jobs/{job_id}")
def compat_get_pipeline_job(job_id: str):
    result = get_table_job(task_id=job_id)
    return _job_to_pipeline_payload(result.model_dump())


@compat_router.get("/table-pipeline/tables")
def compat_list_table_summaries(
    kb_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    rows = table_semantic_service.list_tables(db, kb_id=kb_id, limit=limit)
    tables = []
    for row in rows:
        try:
            artifact = table_semantic_service.get_table_artifact(db, str(row.table_id))
        except Exception:  # noqa: BLE001
            artifact = table_semantic_service.artifact_to_response(row)
        tables.append(_table_to_pipeline_summary(artifact))
    return {"tables": tables}


@compat_router.post("/table-pipeline/search", response_model=TableSearchResponse)
def compat_search_tables(payload: TableSearchRequest, db: Session = Depends(get_db)):
    return search_tables(payload=payload, db=db)


@compat_router.get("/table-pipeline/tables/{table_id}")
def compat_get_table_summary(table_id: str, db: Session = Depends(get_db)):
    try:
        artifact = table_semantic_service.get_table_artifact(db, table_id)
        document = table_semantic_service.get_table_index_document(db, table_id)
        return _table_to_pipeline_summary({**artifact, **document})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="表格不存在") from exc


@compat_router.get("/table-pipeline/tables/{table_id}/artifact")
def compat_get_table_artifact(table_id: str, db: Session = Depends(get_db)):
    artifact = get_table_artifact(table_id=table_id, db=db).model_dump()
    return _artifact_to_pipeline_payload(artifact)


@compat_router.get("/table-pipeline/tables/{table_id}/index-document", response_model=TableIndexDocumentResponse)
def compat_get_table_index_document(table_id: str, db: Session = Depends(get_db)):
    return get_table_index_document(table_id=table_id, db=db)


@compat_router.get("/table-pipeline/tables/{table_id}/tree", response_model=TableTreeResponse)
def compat_get_table_tree(table_id: str, db: Session = Depends(get_db)):
    return get_table_tree(table_id=table_id, db=db)


@compat_router.get("/table-pipeline/tables/{table_id}/source")
def compat_download_table_source(table_id: str, db: Session = Depends(get_db)):
    return _download_table_file(table_id=table_id, kind="source", db=db)


@compat_router.get("/table-pipeline/tables/{table_id}/normalized")
def compat_download_table_normalized_xlsx(table_id: str, db: Session = Depends(get_db)):
    return _download_table_file(table_id=table_id, kind="normalized", db=db)


@compat_router.post("/table-pipeline/answer")
def compat_answer_from_pipeline(
    payload: TableQARequest,
    db: Session = Depends(get_db),
):
    try:
        return table_qa_service.answer_pipeline(
            db,
            question=payload.question,
            kb_id=payload.kb_id,
            top_k=payload.top_k,
            evidence_limit=payload.evidence_limit,
            use_llm=payload.use_llm,
            history=[
                item.model_dump()
                for item in payload.history
            ],
        )
    except RuntimeError as exc:
        logger.exception("pipeline LLM failed")
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@compat_router.post("/table-qa/answer")
def compat_answer_table_question(payload: TableQARequest, db: Session = Depends(get_db)):
    if payload.tree:
        result = table_qa_service.answer_tree(
            db,
            question=payload.question,
            tree=payload.tree,
            metadata=payload.metadata,
            history=[item.model_dump() for item in payload.history],
            top_k=payload.limit or payload.top_k,
            use_llm=payload.use_llm,
        )
        return TableQAResponse(**result).model_dump()
    return answer_table(payload=payload, db=db).model_dump()


@admin_router.post(
    "/table/files/{file_id}/reprocess",
    response_model=TaskSubmitResponse,
)
def reprocess_table_file(
    file_id: int,
    db: Session = Depends(get_db),
):
    try:
        task_id = (
            table_semantic_service
            .reprocess_table_file(
                db=db,
                file_id=int(file_id),
            )
        )

        return TaskSubmitResponse(
            task_id=task_id,
            status="queued",
            message="表格重处理任务已提交",
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
        KnowledgeUsageMismatchError,
        FileProcessorMismatchError,
        FileUsageSnapshotMismatchError,
        TableArtifactContextMismatchError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
