from __future__ import annotations

class DomainError(Exception):
    """Base domain error."""
    code: str = "DOMAIN_ERROR"
    message: str = "Domain error occurred"

    def __init__(self, message: str | None = None, **kwargs) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = kwargs

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            **self.details
        }


class KnowledgeBaseNotFoundError(DomainError):
    code = "KB_NOT_FOUND"
    message = "知识库不存在或已删除"

class KnowledgeBaseConfigurationError(DomainError):
    code = "KB_CONFIG_INVALID"
    message = "知识库配置无效"

class InvalidKnowledgeUsageError(DomainError):
    code = "KB_USAGE_INVALID"
    message = "知识库用途值非法"


class KnowledgeUsageMismatchError(DomainError):
    code = "KB_USAGE_MISMATCH"
    message = "实际用途与操作要求不一致"


class KnowledgeOperationForbiddenError(DomainError):
    code = "KB_OPERATION_FORBIDDEN"
    message = "该用途禁止执行操作"


class KnowledgeUsageImmutableError(DomainError):
    code = "KB_USAGE_IMMUTABLE"
    message = "不允许修改已有知识库用途"


class FileProcessorMismatchError(DomainError):
    code = "FILE_PROCESSOR_MISMATCH"
    message = "文件处理器与知识库用途不一致"


class FileUsageSnapshotMismatchError(DomainError):
    code = "FILE_USAGE_SNAPSHOT_MISMATCH"
    message = "文件用途快照与知识库不一致"


class TaskVersionStaleError(DomainError):
    code = "TASK_VERSION_STALE"
    message = "异步任务版本已过期"

class TaskOwnershipMismatchError(DomainError):
    code = "TASK_OWNERSHIP_MISMATCH"
    message = "异步任务已不再属于当前文件处理流程"


class TaskPayloadInvalidError(DomainError):
    code = "TASK_PAYLOAD_INVALID"
    message = "异步任务参数无效"
    
class DataDictionaryDisabledError(DomainError):
    code = "DATA_DICTIONARY_DISABLED"
    message = "数据字典能力未启用"


class TableArtifactNotFoundError(DomainError):
    code = "TABLE_ARTIFACT_NOT_FOUND"
    message = "表格语义产物不存在"


class TableArtifactContextMismatchError(DomainError):
    code = "TABLE_ARTIFACT_CONTEXT_MISMATCH"
    message = "表格语义产物与文件或知识库上下文不一致"

