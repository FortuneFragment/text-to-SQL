from services.document_qa.document_qa_service import DocumentQAService
from services.document_qa.table_qa_service import TableQAService
from services.document_qa.table_semantic_service import TableSemanticService

table_semantic_service = TableSemanticService()
table_qa_service = TableQAService(table_semantic_service)
document_qa_service = DocumentQAService(table_qa_service)

__all__ = [
    "DocumentQAService",
    "TableQAService",
    "TableSemanticService",
    "document_qa_service",
    "table_qa_service",
    "table_semantic_service",
]
