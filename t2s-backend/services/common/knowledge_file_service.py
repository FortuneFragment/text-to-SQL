from __future__ import annotations

import hashlib
import os
import re
from math import ceil
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from core.config import settings

from core.knowledge_policy import (
    KnowledgeOperation,
    expected_processor,
)
from models.knowledge_file import KnowledgeFile
from repositories.knowledge_file_repo import KnowledgeFileRepository
from repositories.es_repo import es_repo
from repositories.minio_repo import minio_repo
from services.common.knowledge_guard_service import knowledge_guard
from core.es_index_name import is_valid_index_name
from repositories.table_semantic_artifact_repo import (
    TableSemanticArtifactRepository,
)

def _sanitize_filename(value: str) -> str:
    text = os.path.basename(str(value or "").strip())
    text = re.sub(r"[\\/:*?\"<>|]", "_", text)
    return text or "unnamed_file"


class KnowledgeFileService:
    async def calculate_md5(self, file: UploadFile) -> str:
        digest = hashlib.md5(usedforsecurity=False)
        while chunk := await file.read(8192):
            digest.update(chunk)
        await file.seek(0)
        return digest.hexdigest()

    def _resolve_upload_context(
            self,
            db: Session,
            kb_id: int | None,
    ):
        if kb_id is None:
            raise ValueError(
                "上传文件时必须明确指定 kb_id"
            )

        resolved_kb_id = int(kb_id)

        if resolved_kb_id <= 0:
            raise ValueError(
                "kb_id must be greater than 0"
            )

        return knowledge_guard.resolve_kb_for_operation(
            db,
            resolved_kb_id,
            KnowledgeOperation.GENERIC_UPLOAD,
        )

    def _validate_file_meta(self, file: UploadFile) -> str:
        filename = str(file.filename or "").strip()
        if not filename:
            raise ValueError("Found empty filename in upload list")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        allowed = {item.lower().strip() for item in settings.ALLOWED_FILE_TYPES}
        if ext not in allowed:
            raise ValueError(
                f"Unsupported file type: .{ext}. Allowed: {', '.join(sorted(allowed))}"
            )
        return ext

    async def batch_upload(
        self,
        *,
        db: Session,
        files: list[UploadFile],
        kb_id: int | None = None,
        custom_chunk_size: int | None = None,
        custom_chunk_overlap: int | None = None,
    ) -> list[dict]:
        if not files:
            raise ValueError("Please select at least one file")

        if custom_chunk_size is not None and custom_chunk_overlap is not None:
            if int(custom_chunk_overlap) >= int(custom_chunk_size):
                raise ValueError("custom_chunk_overlap must be smaller than custom_chunk_size")

        guard_ctx = self._resolve_upload_context(
            db,
            kb_id,
        )

        kb = guard_ctx.kb
        usage = guard_ctx.usage
        processor = expected_processor(usage)
        resolved_kb_id = int(kb.id)

        file_repo = KnowledgeFileRepository(db)
        results: list[dict] = []

        for upload in files:
            object_name: str | None = None
            created: KnowledgeFile | None = None

            try:
                ext = self._validate_file_meta(upload)
                md5 = await self.calculate_md5(upload)

                if file_repo.check_exists_by_md5_in_context(
                        kb_id=resolved_kb_id,
                        md5=md5,
                        usage_snapshot=usage.value,
                        processor_type=processor.value,
                ):
                    results.append(
                        {
                            "filename": upload.filename,
                            "status": "skipped",
                            "reason": (
                                "File already exists in this "
                                "knowledge base"
                            ),
                        }
                    )
                    continue

                raw = await upload.read()
                await upload.seek(0)

                max_bytes = (
                        int(settings.MAX_UPLOAD_FILE_SIZE_MB)
                        * 1024
                        * 1024
                )

                if len(raw) > max_bytes:
                    raise ValueError(
                        "File exceeds size limit: "
                        f"{settings.MAX_UPLOAD_FILE_SIZE_MB}MB"
                    )

                safe_name = _sanitize_filename(
                    upload.filename or ""
                )

                object_name = (
                    f"{usage.value}/"
                    f"kb_{resolved_kb_id}/"
                    f"{md5}/"
                    f"{safe_name}"
                )

                minio_repo.upload_file_bytes(
                    object_name,
                    raw,
                    content_type=(
                            upload.content_type
                            or "application/octet-stream"
                    ),
                )
                celery_task_id = uuid4().hex
                entity = KnowledgeFile(
                    kb_id=resolved_kb_id,
                    file_name=safe_name,
                    file_type=ext,
                    file_size=len(raw),
                    md5=md5,
                    minio_bucket=minio_repo.bucket_name,
                    minio_object_name=object_name,
                    status=0,
                    task_id=celery_task_id,
                    custom_chunk_size=(
                        int(custom_chunk_size)
                        if custom_chunk_size is not None
                        else None
                    ),
                    custom_chunk_overlap=(
                        int(custom_chunk_overlap)
                        if custom_chunk_overlap is not None
                        else None
                    ),
                    is_deleted=False,
                    usage_snapshot=usage.value,
                    processor_type=processor.value,
                    process_version=1,
                )

                created = file_repo.create_file(entity)

                from tasks.document_tasks import (
                    process_document_task,
                )

                try:
                    process_document_task.apply_async(
                        kwargs={
                            "file_id": int(created.id),
                            "expected_usage": usage.value,
                            "expected_processor_type": (
                                processor.value
                            ),
                            "process_version": 1,
                        },
                        task_id=celery_task_id,
                    )
                except Exception as exc:
                    file_repo.update_status_for_task(
                        int(created.id),
                        task_id=celery_task_id,
                        process_version=1,
                        status=3,
                        error_msg=(
                            "Failed to publish document task: "
                            f"{exc}"
                        )[:1000],
                    )
                    raise

                results.append(
                    {
                        "filename": upload.filename,
                        "status": "success",
                        "file_id": int(created.id),
                        "task_id": celery_task_id,
                    }
                )

            except Exception as exc:  # noqa: BLE001
                # MinIO 已上传但数据库记录未创建时，
                # 删除孤立对象。
                if object_name is not None and created is None:
                    try:
                        minio_repo.delete_file(object_name)
                    except Exception:
                        pass

                results.append(
                    {
                        "filename": upload.filename,
                        "status": "failed",
                        "reason": str(exc),
                    }
                )

        return results

    def list_files(
            self,
            *,
            db: Session,
            kb_id: int,
            page: int,
            page_size: int,
    ) -> tuple[
        list[KnowledgeFile],
        int,
        dict[int, int],
    ]:
        guard_ctx = knowledge_guard.resolve_kb_for_operation(
            db,
            int(kb_id),
            KnowledgeOperation.GENERIC_FILE_LIST,
        )

        processor = expected_processor(
            guard_ctx.usage
        )

        repo = KnowledgeFileRepository(db)

        rows, total = (
            repo.list_by_kb_context_paginated(
                kb_id=int(guard_ctx.kb.id),
                usage_snapshot=guard_ctx.usage.value,
                processor_type=processor.value,
                page=int(page),
                page_size=int(page_size),
            )
        )

        chunk_counts = repo.count_chunks_by_file_ids(
            file_ids=[int(row.id) for row in rows],
            kb_id=int(guard_ctx.kb.id),
            usage_snapshot=guard_ctx.usage.value,
            processor_type=processor.value,
        )

        return rows, total, chunk_counts

    @staticmethod
    def build_total_pages(total: int, page_size: int) -> int:
        if total <= 0:
            return 0
        return int(ceil(total / page_size))

    def delete_file(
            self,
            *,
            db: Session,
            file_id: int,
    ) -> None:
        guard_ctx = (
            knowledge_guard.resolve_file_for_operation(
                db,
                int(file_id),
                KnowledgeOperation.GENERIC_FILE_DELETE,
            )
        )

        file_entity = guard_ctx.file
        kb_entity = guard_ctx.kb

        if file_entity is None:
            raise RuntimeError(
                "Knowledge file guard context is incomplete"
            )

        file_repo = KnowledgeFileRepository(db)

        # ES 删除失败时禁止继续软删除数据库记录，
        # 否则已删除文件仍可能被检索到。
        try:
            es_repo.delete_chunks_by_file_id(
                int(file_entity.id),
                kb_id=int(kb_entity.id),
                index_name=str(
                    kb_entity.collection_name
                ),
            )
        except Exception as exc:
            raise RuntimeError(
                "Failed to delete file chunks from "
                f"Elasticsearch: {exc}"
            ) from exc

        file_repo.delete_chunks_by_file_id(
            int(file_entity.id),
            kb_id=int(kb_entity.id),
        )

        # 清理历史污染情况下可能存在的表格产物。
        TableSemanticArtifactRepository(
            db
        ).soft_delete_by_file_id(
            int(file_entity.id)
        )

        minio_repo.delete_file(
            file_entity.minio_object_name
        )

        file_repo.soft_delete(file_entity)

    def update_strategy_and_reprocess(
        self,
        *,
        db: Session,
        file_id: int,
        custom_chunk_size: int,
        custom_chunk_overlap: int,
    ) -> tuple[KnowledgeFile, str]:
        file_repo = KnowledgeFileRepository(db)
        
        # Enforce Guard checks
        guard_ctx = knowledge_guard.resolve_file_for_operation(db, file_id, KnowledgeOperation.GENERIC_REPROCESS)
        file_entity = guard_ctx.file

        if file_entity is None:
            raise ValueError("File not found")

        if custom_chunk_overlap >= custom_chunk_size:
            raise ValueError("custom_chunk_overlap must be smaller than custom_chunk_size")

        updated = file_repo.update_strategy(
            file_entity,
            chunk_size=int(custom_chunk_size),
            chunk_overlap=int(custom_chunk_overlap),
        )

        celery_task_id = uuid4().hex

        new_version = file_repo.submit_task(
            int(updated.id),
            celery_task_id,
        )

        from tasks.document_tasks import (
            reprocess_document_task,
        )

        try:
            reprocess_document_task.apply_async(
                kwargs={
                    "file_id": int(updated.id),
                    "expected_usage": (
                        guard_ctx.usage.value
                    ),
                    "expected_processor_type": (
                        guard_ctx.processor_type.value
                    ),
                    "process_version": new_version,
                },
                task_id=celery_task_id,
            )
        except Exception as exc:
            file_repo.update_status_for_task(
                int(updated.id),
                task_id=celery_task_id,
                process_version=new_version,
                status=3,
                error_msg=(
                    "Failed to publish reprocess task: "
                    f"{exc}"
                )[:1000],
            )
            raise
        
        return updated, celery_task_id

    def reprocess_file(self, *, db: Session, file_id: int) -> str:
        file_repo = KnowledgeFileRepository(db)
        
        # Enforce Guard checks
        guard_ctx = knowledge_guard.resolve_file_for_operation(db, file_id, KnowledgeOperation.GENERIC_REPROCESS)
        file_entity = guard_ctx.file

        if file_entity is None:
            raise ValueError("File not found")

        celery_task_id = uuid4().hex

        new_version = file_repo.submit_task(
            int(file_entity.id),
            celery_task_id,
        )

        from tasks.document_tasks import (
            reprocess_document_task,
        )

        try:
            reprocess_document_task.apply_async(
                kwargs={
                    "file_id": int(file_entity.id),
                    "expected_usage": (
                        guard_ctx.usage.value
                    ),
                    "expected_processor_type": (
                        guard_ctx.processor_type.value
                    ),
                    "process_version": new_version,
                },
                task_id=celery_task_id,
            )
        except Exception as exc:
            file_repo.update_status_for_task(
                int(file_entity.id),
                task_id=celery_task_id,
                process_version=new_version,
                status=3,
                error_msg=(
                    "Failed to publish reprocess task: "
                    f"{exc}"
                )[:1000],
            )
            raise

        return celery_task_id

    def get_file(
            self,
            *,
            db: Session,
            file_id: int,
    ) -> tuple[KnowledgeFile, int]:
        guard_ctx = (
            knowledge_guard.resolve_file_for_operation(
                db,
                int(file_id),
                KnowledgeOperation.GENERIC_FILE_READ,
            )
        )

        file_entity = guard_ctx.file
        processor = guard_ctx.processor_type

        if file_entity is None or processor is None:
            raise RuntimeError(
                "Knowledge file guard context is incomplete"
            )

        chunk_count = (
            KnowledgeFileRepository(db)
            .count_chunks_by_file_id(
                int(file_entity.id),
                kb_id=int(guard_ctx.kb.id),
                usage_snapshot=guard_ctx.usage.value,
                processor_type=processor.value,
            )
        )

        return file_entity, chunk_count

    def list_file_chunks(
            self,
            *,
            db: Session,
            file_id: int,
            page: int,
            page_size: int,
    ):
        guard_ctx = (
            knowledge_guard.resolve_file_for_operation(
                db,
                int(file_id),
                KnowledgeOperation.GENERIC_CHUNK_READ,
            )
        )

        file_entity = guard_ctx.file
        processor = guard_ctx.processor_type

        if file_entity is None or processor is None:
            raise RuntimeError(
                "Knowledge file guard context is incomplete"
            )

        return (
            KnowledgeFileRepository(db)
            .list_chunks_by_file_paginated(
                file_id=int(file_entity.id),
                page=int(page),
                page_size=int(page_size),
                kb_id=int(guard_ctx.kb.id),
                usage_snapshot=guard_ctx.usage.value,
                processor_type=processor.value,
            )
        )
knowledge_file_service = KnowledgeFileService()
