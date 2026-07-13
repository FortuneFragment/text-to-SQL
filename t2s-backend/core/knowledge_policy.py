from __future__ import annotations

from enum import Enum
from core.domain_errors import (
    InvalidKnowledgeUsageError,
    KnowledgeOperationForbiddenError,
    KnowledgeUsageMismatchError,
)

class KnowledgeUsage(str, Enum):
    TABLE_ROUTE = "table_route"
    FEW_SHOT = "few_shot"
    DATA_DICTIONARY = "data_dictionary"
    DOCUMENT_QA = "document_qa"
    TABLE_SEMANTIC_TREE = "table_semantic_tree"


class KnowledgeOperation(str, Enum):
    GENERIC_UPLOAD = "generic_upload"
    GENERIC_REPROCESS = "generic_reprocess"

    GENERIC_FILE_LIST = "generic_file_list"
    GENERIC_FILE_READ = "generic_file_read"
    GENERIC_CHUNK_READ = "generic_chunk_read"
    GENERIC_FILE_DELETE = "generic_file_delete"

    DOCUMENT_QA_SEARCH = "document_qa_search"
    TABLE_ROUTE_SEARCH = "table_route_search"
    FEW_SHOT_WRITE = "few_shot_write"
    FEW_SHOT_SEARCH = "few_shot_search"
    TABLE_UPLOAD = "table_upload"
    TABLE_READ = "table_read"
    TABLE_REPROCESS = "table_reprocess"
    DATA_DICTIONARY_WRITE = "data_dictionary_write"
    DATA_DICTIONARY_SEARCH = "data_dictionary_search"


class ProcessorType(str, Enum):
    GENERIC_DOCUMENT = "generic_document"
    FEW_SHOT = "few_shot"
    TABLE_SEMANTIC = "table_semantic"
    DATA_DICTIONARY = "data_dictionary"


# Map each usage to its allowed processor type
USAGE_PROCESSOR_MAP = {
    KnowledgeUsage.TABLE_ROUTE: ProcessorType.GENERIC_DOCUMENT,
    KnowledgeUsage.DOCUMENT_QA: ProcessorType.GENERIC_DOCUMENT,
    KnowledgeUsage.FEW_SHOT: ProcessorType.FEW_SHOT,
    KnowledgeUsage.TABLE_SEMANTIC_TREE: ProcessorType.TABLE_SEMANTIC,
    KnowledgeUsage.DATA_DICTIONARY: ProcessorType.DATA_DICTIONARY,
}

# Map each usage to allowed operations
USAGE_OPERATIONS_MAP = {
    KnowledgeUsage.TABLE_ROUTE: {
        KnowledgeOperation.GENERIC_UPLOAD,
        KnowledgeOperation.GENERIC_REPROCESS,
        KnowledgeOperation.GENERIC_FILE_LIST,
        KnowledgeOperation.GENERIC_FILE_READ,
        KnowledgeOperation.GENERIC_CHUNK_READ,
        KnowledgeOperation.GENERIC_FILE_DELETE,
        KnowledgeOperation.TABLE_ROUTE_SEARCH,
    },
    KnowledgeUsage.DOCUMENT_QA: {
        KnowledgeOperation.GENERIC_UPLOAD,
        KnowledgeOperation.GENERIC_REPROCESS,
        KnowledgeOperation.GENERIC_FILE_LIST,
        KnowledgeOperation.GENERIC_FILE_READ,
        KnowledgeOperation.GENERIC_CHUNK_READ,
        KnowledgeOperation.GENERIC_FILE_DELETE,
        KnowledgeOperation.DOCUMENT_QA_SEARCH,
    },
    KnowledgeUsage.FEW_SHOT: {
        KnowledgeOperation.FEW_SHOT_WRITE,
        KnowledgeOperation.FEW_SHOT_SEARCH,
    },
    KnowledgeUsage.TABLE_SEMANTIC_TREE: {
        KnowledgeOperation.TABLE_UPLOAD,
        KnowledgeOperation.TABLE_READ,
        KnowledgeOperation.TABLE_REPROCESS,
        KnowledgeOperation.DOCUMENT_QA_SEARCH,
    },
    KnowledgeUsage.DATA_DICTIONARY: {
        KnowledgeOperation.DATA_DICTIONARY_WRITE,
        KnowledgeOperation.DATA_DICTIONARY_SEARCH,
    },
}


def parse_usage(value: object) -> KnowledgeUsage:
    """Strictly parse usage, raising InvalidKnowledgeUsageError on failure."""
    if isinstance(value, KnowledgeUsage):
        return value
    val_str = str(value or "").strip().lower()
    try:
        return KnowledgeUsage(val_str)
    except ValueError as exc:
        raise InvalidKnowledgeUsageError(f"Invalid knowledge usage: '{value}'") from exc


def require_operation(usage: KnowledgeUsage, operation: KnowledgeOperation) -> None:
    """Ensure that the given operation is allowed for the usage."""
    allowed_ops = USAGE_OPERATIONS_MAP.get(usage, set())
    if operation not in allowed_ops:
        raise KnowledgeOperationForbiddenError(
            f"Operation '{operation.value}' is not allowed for knowledge base usage '{usage.value}'"
        )


def expected_processor(usage: KnowledgeUsage) -> ProcessorType:
    """Get the expected processor type for a usage."""
    return USAGE_PROCESSOR_MAP[usage]
