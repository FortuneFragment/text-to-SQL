from __future__ import annotations

import hashlib
import os
import re
from math import ceil
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from core.config import settings
from core.milvus_name import normalize_collection_name
from models.knowledge_file import KnowledgeFile
from repositories.knowledge_base_repo import KnowledgeBaseRepository
from repositories.knowledge_file_repo import KnowledgeFileRepository
from repositories.milvus_repo import milvus_repo
from repositories.minio_repo import minio_repo
from services.knowledge_service import knowledge_service


def _sanitize_filename(value: str) -> str:
    """中文备注：处理_sanitize_filename相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    text = os.path.basename(str(value or "").strip())
    text = re.sub(r"[\\/:*?\"<>|]", "_", text)
    return text or "unnamed_file"


class KnowledgeFileService:
    async def calculate_md5(self, file: UploadFile) -> str:
        """中文备注：处理calculate_md5相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        digest = hashlib.md5(usedforsecurity=False)
        while chunk := await file.read(8192):
            digest.update(chunk)
        await file.seek(0)
        return digest.hexdigest()

    def _resolve_kb(self, db: Session, kb_id: Optional[int]) -> tuple[int, str]:
        """中文备注：处理_resolve_kb相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        kb_repo = KnowledgeBaseRepository(db)
        if kb_id is None:
            kb = knowledge_service.ensure_default_kb(db)
        else:
            kb = kb_repo.get_by_id(int(kb_id))
            if kb is None:
                raise ValueError(f"Knowledge base not found: {kb_id}")

        normalized = normalize_collection_name(str(kb.collection_name))
        if normalized != str(kb.collection_name):
            used_names = {item.collection_name for item in kb_repo.list_all() if int(item.id) != int(kb.id)}
            candidate = normalized
            index = 1
            while candidate in used_names:
                suffix = f"_{index}"
                limit = max(1, 128 - len(suffix))
                candidate = f"{normalized[:limit]}{suffix}"
                index += 1
            kb.collection_name = candidate
            kb = kb_repo.update(kb)
        return int(kb.id), str(kb.collection_name)

    def _validate_file_meta(self, file: UploadFile) -> str:
        """中文备注：处理_validate_file_meta相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
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
        """中文备注：处理batch_upload相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        if not files:
            raise ValueError("Please select at least one file")

        if custom_chunk_size is not None and custom_chunk_overlap is not None:
            if int(custom_chunk_overlap) >= int(custom_chunk_size):
                raise ValueError("custom_chunk_overlap must be smaller than custom_chunk_size")

        resolved_kb_id, _ = self._resolve_kb(db, kb_id)
        file_repo = KnowledgeFileRepository(db)
        results: list[dict] = []

        for upload in files:
            try:
                ext = self._validate_file_meta(upload)
                md5 = await self.calculate_md5(upload)

                if file_repo.check_exists_by_md5(resolved_kb_id, md5):
                    results.append(
                        {
                            "filename": upload.filename,
                            "status": "skipped",
                            "reason": "File already exists in this knowledge base",
                        }
                    )
                    continue

                raw = await upload.read()
                await upload.seek(0)

                max_bytes = int(settings.MAX_UPLOAD_FILE_SIZE_MB) * 1024 * 1024
                if len(raw) > max_bytes:
                    raise ValueError(
                        f"File exceeds size limit: {settings.MAX_UPLOAD_FILE_SIZE_MB}MB"
                    )

                safe_name = _sanitize_filename(upload.filename or "")
                object_name = f"kb_{resolved_kb_id}/{md5}/{safe_name}"
                minio_repo.upload_file_bytes(
                    object_name,
                    raw,
                    content_type=upload.content_type or "application/octet-stream",
                )

                entity = KnowledgeFile(
                    kb_id=resolved_kb_id,
                    file_name=safe_name,
                    file_type=ext,
                    file_size=len(raw),
                    md5=md5,
                    minio_bucket=minio_repo.bucket_name,
                    minio_object_name=object_name,
                    status=0,
                    custom_chunk_size=(int(custom_chunk_size) if custom_chunk_size is not None else None),
                    custom_chunk_overlap=(
                        int(custom_chunk_overlap) if custom_chunk_overlap is not None else None
                    ),
                    is_deleted=False,
                )
                created = file_repo.create_file(entity)

                from tasks.document_tasks import process_document_task

                task = process_document_task.delay(int(created.id))
                file_repo.set_task_id(int(created.id), task.id)

                results.append(
                    {
                        "filename": upload.filename,
                        "status": "success",
                        "file_id": int(created.id),
                        "task_id": task.id,
                    }
                )
            except Exception as exc:  # noqa: BLE001
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
    ) -> tuple[list[KnowledgeFile], int]:
        """中文备注：处理list_files相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        rows, total = KnowledgeFileRepository(db).list_by_kb_paginated(kb_id=kb_id, page=page, page_size=page_size)
        return rows, total

    @staticmethod
    def build_total_pages(total: int, page_size: int) -> int:
        """中文备注：处理build_total_pages相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        if total <= 0:
            return 0
        return int(ceil(total / page_size))

    def delete_file(self, *, db: Session, file_id: int) -> None:
        """中文备注：处理delete_file相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        file_repo = KnowledgeFileRepository(db)
        kb_repo = KnowledgeBaseRepository(db)

        file_entity = file_repo.get_by_id(file_id)
        if file_entity is None:
            raise ValueError("File not found")

        kb_entity = kb_repo.get_by_id(int(file_entity.kb_id))
        if kb_entity is None:
            raise ValueError("Knowledge base not found")

        try:
            milvus_repo.delete_chunks_by_file_id(
                int(file_entity.id),
                collection_name=kb_entity.collection_name,
                vector_dim=int(settings.MILVUS_VECTOR_DIM),
            )
        except Exception:
            # Keep MySQL/MinIO cleanup idempotent even if Milvus item already gone.
            pass

        file_repo.delete_chunks_by_file_id(int(file_entity.id))
        minio_repo.delete_file(file_entity.minio_object_name)
        file_repo.soft_delete(file_entity)

    def update_strategy_and_reprocess(
        self,
        *,
        db: Session,
        file_id: int,
        custom_chunk_size: int,
        custom_chunk_overlap: int,
    ) -> tuple[KnowledgeFile, str]:
        """中文备注：处理update_strategy_and_reprocess相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        file_repo = KnowledgeFileRepository(db)
        file_entity = file_repo.get_by_id(file_id)
        if file_entity is None:
            raise ValueError("File not found")

        if custom_chunk_overlap >= custom_chunk_size:
            raise ValueError("custom_chunk_overlap must be smaller than custom_chunk_size")

        updated = file_repo.update_strategy(
            file_entity,
            chunk_size=int(custom_chunk_size),
            chunk_overlap=int(custom_chunk_overlap),
        )

        from tasks.document_tasks import reprocess_document_task

        task = reprocess_document_task.delay(int(updated.id))
        file_repo.set_task_id(int(updated.id), task.id)
        return updated, task.id

    def reprocess_file(self, *, db: Session, file_id: int) -> str:
        """中文备注：处理reprocess_file相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        file_repo = KnowledgeFileRepository(db)
        file_entity = file_repo.get_by_id(file_id)
        if file_entity is None:
            raise ValueError("File not found")

        from tasks.document_tasks import reprocess_document_task

        task = reprocess_document_task.delay(int(file_entity.id))
        file_repo.update_status(
            int(file_entity.id),
            status=0,
            error_msg=None,
            task_id=task.id,
        )
        return task.id


knowledge_file_service = KnowledgeFileService()
