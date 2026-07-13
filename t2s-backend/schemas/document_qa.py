from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentQATurn(BaseModel):
    question: str = Field(default="", max_length=4000)
    answer: str = Field(default="", max_length=8000)


class DocumentQARequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    kb_id: int | None = Field(default=None, ge=1)
    history: list[DocumentQATurn] = Field(default_factory=list, max_length=20)
    top_k: int = Field(default=6, ge=1, le=20)


class DocumentQAEvidence(BaseModel):
    kb_id: int
    file_id: int | None = None
    chunk_id: int | None = None
    score: float = 0.0
    text: str = ""


class DocumentQAResponse(BaseModel):
    answer: str
    evidences: list[DocumentQAEvidence] = Field(default_factory=list)


class TableUploadResponse(BaseModel):
    file_id: int
    task_id: str
    table_id: str
    batch_id: str = ""
    table_ids: list[str] = Field(default_factory=list)
    sheet_names: list[str] = Field(default_factory=list)
    status: str = "queued"
    message: str = ""


class TableSemanticArtifactResponse(BaseModel):
    id: int
    kb_id: int
    file_id: int

    usage_snapshot: str
    processor_type: str

    table_id: str
    file_name: str
    sheet_name: str
    table_title: str
    summary_text: str
    candidate_fields: list[str] = Field(default_factory=list)
    tree_path_text: list[str] = Field(default_factory=list)
    tree_metric_names: list[str] = Field(default_factory=list)
    tree_object_name: str
    row_count: int
    column_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TableListResponse(BaseModel):
    items: list[TableSemanticArtifactResponse] = Field(default_factory=list)


class TableTreeResponse(BaseModel):
    table_id: str
    tree: dict[str, Any] = Field(default_factory=dict)
    tree_with_cell_refs: dict[str, Any] = Field(default_factory=dict)


class TableArtifactDetailResponse(TableSemanticArtifactResponse):
    batch_id: str = ""
    source_object_name: str = ""
    normalized_object_name: str = ""
    tree: dict[str, Any] = Field(default_factory=dict)
    tree_with_cell_refs: dict[str, Any] = Field(default_factory=dict)
    parse_plan: dict[str, Any] = Field(default_factory=dict)
    parse_mode: str = ""
    large_table_reason: str = ""
    markdown_table: str = ""
    normalized_headers: str = ""
    hierarchy_definition: str = ""
    final_json_tree: str = ""
    coverage: dict[str, Any] = Field(default_factory=dict)
    validation_warnings: list[str] = Field(default_factory=list)


class TableQARequest(BaseModel):
    table_id: str | None = Field(default=None, max_length=64)
    kb_id: int | None = Field(default=None, ge=1)
    question: str = Field(min_length=1, max_length=4000)
    tree: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    history: list[DocumentQATurn] = Field(default_factory=list, max_length=20)
    top_k: int = Field(default=8, ge=1, le=50)
    limit: int = Field(default=12, ge=1, le=50)
    evidence_limit: int = Field(default=12, ge=1, le=50)
    use_llm: bool = True


class TableQACandidate(BaseModel):
    text: str
    score: float = 0.0
    source: str = ""
    table_id: str | None = None
    table_title: str | None = None


class TableQAResponse(BaseModel):
    table_id: str | None = None
    table_ids: list[str] = Field(default_factory=list)
    answer: str
    mode: str
    evidence_paths: list[str] = Field(default_factory=list)
    candidates: list[TableQACandidate] = Field(default_factory=list)


class TableSourceResponse(BaseModel):
    table_id: str
    file_id: int
    file_name: str
    url: str


class TableSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    kb_id: int | None = Field(default=None, ge=1)
    top_k: int = Field(default=8, ge=1, le=50)


class TableSearchHit(BaseModel):
    kb_id: int | None = None
    file_id: int | None = None
    table_id: str
    table_title: str = ""
    file_name: str = ""
    sheet_name: str = ""
    summary_text: str = ""
    candidate_fields: list[str] = Field(default_factory=list)
    tree_metric_names: list[str] = Field(default_factory=list)
    tree_path_text: list[str] = Field(default_factory=list)
    tree_leaf_text: list[str] = Field(default_factory=list)
    tree_search_text: str = ""
    tree_object_name: str = ""
    source_object_name: str = ""
    normalized_object_name: str = ""
    parse_mode: str = ""
    large_table_reason: str = ""
    embedding_error: str = ""
    row_count: int = 0
    column_count: int = 0
    score: float = 0.0
    source: str = ""


class TableSearchResponse(BaseModel):
    items: list[TableSearchHit] = Field(default_factory=list)


class TableIndexDocumentResponse(BaseModel):
    document: dict[str, Any] = Field(default_factory=dict)


class TableJobResponse(BaseModel):
    task_id: str = ""
    batch_id: str = ""

    state: str
    ready: bool = False
    successful: bool = False

    result: Any | None = None
    error: str | None = None

    file_id: int | None = None
    file_name: str | None = None

    table_id: str | None = None
    table_ids: list[str] = Field(
        default_factory=list
    )
    sheet_names: list[str] = Field(
        default_factory=list
    )

    total_sheets: int = 0
    completed_sheets: int = 0
    progress: float = 0.0

    current_table_id: str | None = None
    current_sheet_name: str | None = None

    tables: list[
        TableSemanticArtifactResponse
    ] = Field(default_factory=list)

    created_at: datetime | None = None
    updated_at: datetime | None = None


class TableJobListResponse(BaseModel):
    items: list[TableJobResponse] = Field(default_factory=list)
