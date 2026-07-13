from __future__ import annotations

import logging
from dataclasses import dataclass
from sqlalchemy.orm import Session

from core.config import settings
from core.domain_errors import (
    KnowledgeBaseNotFoundError,
    KnowledgeUsageMismatchError,
    FileProcessorMismatchError,
    FileUsageSnapshotMismatchError,
    TaskOwnershipMismatchError,
    TaskPayloadInvalidError,
    TaskVersionStaleError,
)
from core.knowledge_policy import (
    KnowledgeUsage,
    KnowledgeOperation,
    ProcessorType,
    parse_usage,
    require_operation,
    expected_processor,
)
from models.knowledge_base import KnowledgeBase
from models.knowledge_file import KnowledgeFile
from repositories.knowledge_base_repo import KnowledgeBaseRepository
from repositories.knowledge_file_repo import KnowledgeFileRepository

logger = logging.getLogger("kb.guard")


@dataclass
class GuardContext:
    kb: KnowledgeBase
    usage: KnowledgeUsage
    file: KnowledgeFile | None = None
    processor_type: ProcessorType | None = None


class KnowledgeGuardService:
    def _log_audit(
        self,
        operation: KnowledgeOperation,
        kb_id: int,
        file_id: int | None = None,
        actual_usage: str | None = None,
        processor_type: str | None = None,
        result: str = "success",
        error_code: str | None = None,
    ) -> None:
        if not getattr(settings, "KB_USAGE_AUDIT_LOG_ENABLED", True):
            return
        logger.info(
            "KB_AUDIT: operation=%s kb_id=%s file_id=%s actual_usage=%s processor_type=%s result=%s error_code=%s",
            operation.value,
            kb_id,
            file_id,
            actual_usage,
            processor_type,
            result,
            error_code,
        )

    def resolve_kb_for_operation(
            self,
            db: Session,
            kb_id: int,
            operation: KnowledgeOperation,
    ) -> GuardContext:
        kb_repo = KnowledgeBaseRepository(db)
        kb = kb_repo.get_by_id(kb_id)

        if kb is None:
            self._log_audit(
                operation,
                kb_id,
                result="denied",
                error_code="KB_NOT_FOUND",
            )
            raise KnowledgeBaseNotFoundError(
                f"Knowledge base ID {kb_id} not found"
            )

        usage = parse_usage(kb.usage)

        try:
            require_operation(usage, operation)
        except Exception as exc:
            self._log_audit(
                operation,
                kb_id,
                actual_usage=usage.value,
                result="denied",
                error_code=getattr(
                    exc,
                    "code",
                    "KB_OPERATION_FORBIDDEN",
                ),
            )
            raise

        self._log_audit(
            operation,
            kb_id,
            actual_usage=usage.value,
            result="allowed",
        )

        return GuardContext(
            kb=kb,
            usage=usage,
        )

    def resolve_file_for_operation(
            self,
            db: Session,
            file_id: int,
            operation: KnowledgeOperation,
    ) -> GuardContext:
        file_repo = KnowledgeFileRepository(db)
        row = file_repo.get_with_kb(file_id)

        if row is None:
            self._log_audit(
                operation,
                kb_id=0,
                file_id=file_id,
                result="denied",
                error_code="FILE_NOT_FOUND",
            )
            raise KnowledgeBaseNotFoundError(
                f"File ID {file_id} or its associated KB not found"
            )

        file_entity, kb_entity = row

        if not file_entity.usage_snapshot:
            raise FileUsageSnapshotMismatchError(
                f"文件缺少用途快照：file_id={file_entity.id}"
            )

        if not file_entity.processor_type:
            raise FileProcessorMismatchError(
                f"文件缺少处理器类型：file_id={file_entity.id}"
            )

        kb_usage = parse_usage(kb_entity.usage)
        file_usage = parse_usage(file_entity.usage_snapshot)

        if file_usage != kb_usage:
            self._log_audit(
                operation,
                kb_id=int(kb_entity.id),
                file_id=file_id,
                actual_usage=kb_usage.value,
                result="denied",
                error_code="FILE_USAGE_SNAPSHOT_MISMATCH",
            )
            raise FileUsageSnapshotMismatchError(
                "File usage snapshot "
                f"'{file_entity.usage_snapshot}' does not match "
                f"KB usage '{kb_entity.usage}'"
            )

        try:
            processor = ProcessorType(file_entity.processor_type)
        except (TypeError, ValueError) as exc:
            self._log_audit(
                operation,
                kb_id=int(kb_entity.id),
                file_id=file_id,
                actual_usage=kb_usage.value,
                processor_type=str(file_entity.processor_type),
                result="denied",
                error_code="INVALID_FILE_PROCESSOR",
            )
            raise FileProcessorMismatchError(
                f"Invalid file processor type: "
                f"'{file_entity.processor_type}'"
            ) from exc

        expected = expected_processor(kb_usage)

        if processor != expected:
            self._log_audit(
                operation,
                kb_id=int(kb_entity.id),
                file_id=file_id,
                actual_usage=kb_usage.value,
                processor_type=processor.value,
                result="denied",
                error_code="FILE_PROCESSOR_MISMATCH",
            )
            raise FileProcessorMismatchError(
                f"File processor type '{processor.value}' does not "
                f"match expected processor '{expected.value}' "
                f"for usage '{kb_usage.value}'"
            )

        try:
            require_operation(kb_usage, operation)
        except Exception as exc:
            self._log_audit(
                operation,
                kb_id=int(kb_entity.id),
                file_id=file_id,
                actual_usage=kb_usage.value,
                processor_type=processor.value,
                result="denied",
                error_code=getattr(
                    exc,
                    "code",
                    "KB_OPERATION_FORBIDDEN",
                ),
            )
            raise

        self._log_audit(
            operation,
            kb_id=int(kb_entity.id),
            file_id=file_id,
            actual_usage=kb_usage.value,
            processor_type=processor.value,
            result="allowed",
        )

        return GuardContext(
            kb=kb_entity,
            usage=kb_usage,
            file=file_entity,
            processor_type=processor,
        )

    def resolve_file_for_task(
            self,
            db: Session,
            *,
            file_id: int,
            operation: KnowledgeOperation,
            task_id: str,
            process_version: int,
            expected_usage: str,
            expected_processor_type: str,
    ) -> GuardContext:
        normalized_task_id = str(task_id or "").strip()

        if not normalized_task_id:
            raise TaskPayloadInvalidError(
                "Celery task_id cannot be empty"
            )

        if int(process_version) <= 0:
            raise TaskPayloadInvalidError(
                "process_version must be greater than 0"
            )

        expected_usage_enum = parse_usage(
            expected_usage
        )

        try:
            expected_processor_enum = ProcessorType(
                str(expected_processor_type)
            )
        except (TypeError, ValueError) as exc:
            raise TaskPayloadInvalidError(
                "Invalid expected processor type: "
                f"{expected_processor_type!r}"
            ) from exc

        expected_processor_by_usage = expected_processor(
            expected_usage_enum
        )

        if (
                expected_processor_enum
                != expected_processor_by_usage
        ):
            raise FileProcessorMismatchError(
                f"Processor '{expected_processor_enum.value}' "
                f"does not match usage "
                f"'{expected_usage_enum.value}'"
            )

        # 先执行文件、知识库、用途、处理器和操作权限校验。
        guard_ctx = self.resolve_file_for_operation(
            db,
            int(file_id),
            operation,
        )

        file_entity = guard_ctx.file

        if file_entity is None:
            raise KnowledgeBaseNotFoundError(
                f"File ID {file_id} not found"
            )

        if guard_ctx.usage != expected_usage_enum:
            raise KnowledgeUsageMismatchError(
                f"Task expected usage "
                f"'{expected_usage_enum.value}', "
                f"but KB usage is "
                f"'{guard_ctx.usage.value}'"
            )

        if (
                str(file_entity.usage_snapshot)
                != expected_usage_enum.value
        ):
            raise KnowledgeUsageMismatchError(
                f"Task expected usage "
                f"'{expected_usage_enum.value}', "
                f"but file snapshot is "
                f"'{file_entity.usage_snapshot}'"
            )

        if (
                guard_ctx.processor_type
                != expected_processor_enum
        ):
            actual_processor = (
                guard_ctx.processor_type.value
                if guard_ctx.processor_type is not None
                else None
            )

            raise FileProcessorMismatchError(
                f"Task expected processor "
                f"'{expected_processor_enum.value}', "
                f"but file processor is "
                f"'{actual_processor}'"
            )

        if (
                int(file_entity.process_version)
                != int(process_version)
        ):
            raise TaskVersionStaleError(
                f"Task version stale: expected "
                f"{process_version}, actual "
                f"{file_entity.process_version}"
            )

        current_task_id = str(
            file_entity.task_id or ""
        ).strip()

        if current_task_id != normalized_task_id:
            raise TaskOwnershipMismatchError(
                f"Task ownership mismatch: expected "
                f"'{normalized_task_id}', actual "
                f"'{current_task_id}'"
            )

        return guard_ctx
    
knowledge_guard = KnowledgeGuardService()
