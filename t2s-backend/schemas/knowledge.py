from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from core.knowledge_usage import KB_USAGE_TABLE_ROUTE
from pydantic import BaseModel, ConfigDict, Field, model_validator

KnowledgeBaseUsage = Literal[
    "table_route",
    "few_shot",
    "data_dictionary",
    "document_qa",
    "table_semantic_tree",
]


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    collection_name: Optional[str] = Field(default=None, max_length=128)
    usage: KnowledgeBaseUsage = KB_USAGE_TABLE_ROUTE
    default_chunk_size: int = Field(default=800, ge=100, le=8000)
    default_chunk_overlap: int = Field(default=120, ge=0, le=2000)
    embedding_model: Optional[str] = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_overlap(self) -> "KnowledgeBaseCreateRequest":
        if self.default_chunk_overlap >= self.default_chunk_size:
            raise ValueError("default_chunk_overlap must be smaller than default_chunk_size")
        return self


class KnowledgeBaseUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=128,
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
    )
    default_chunk_size: Optional[int] = Field(
        default=None,
        ge=100,
        le=8000,
    )
    default_chunk_overlap: Optional[int] = Field(
        default=None,
        ge=0,
        le=2000,
    )
    embedding_model: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    @model_validator(mode="after")
    def validate_overlap(self) -> "KnowledgeBaseUpdateRequest":
        if (
            self.default_chunk_size is not None
            and self.default_chunk_overlap is not None
            and self.default_chunk_overlap
            >= self.default_chunk_size
        ):
            raise ValueError(
                "default_chunk_overlap must be smaller "
                "than default_chunk_size"
            )

        return self


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: str = ""
    collection_name: str
    usage: KnowledgeBaseUsage = KB_USAGE_TABLE_ROUTE
    default_chunk_size: int
    default_chunk_overlap: int
    embedding_model: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeFileResponse(BaseModel):
    id: int
    kb_id: int
    file_name: str
    file_type: str
    file_size: int
    status: int
    error_msg: Optional[str] = None
    task_id: Optional[str] = None

    custom_chunk_size: Optional[int] = None
    custom_chunk_overlap: Optional[int] = None

    usage_snapshot: str
    processor_type: str
    process_version: int

    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class FileBatchUploadItem(BaseModel):
    filename: str
    status: str
    file_id: Optional[int] = None
    task_id: Optional[str] = None
    reason: Optional[str] = None


class FilePageResponse(BaseModel):
    items: list[KnowledgeFileResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class FileStrategyUpdateRequest(BaseModel):
    custom_chunk_size: int = Field(..., ge=100, le=8000)
    custom_chunk_overlap: int = Field(..., ge=0, le=2000)

    @model_validator(mode="after")
    def validate_overlap(self) -> "FileStrategyUpdateRequest":
        if self.custom_chunk_overlap >= self.custom_chunk_size:
            raise ValueError("custom_chunk_overlap must be smaller than custom_chunk_size")
        return self


class ChunkResponse(BaseModel):
    id: int
    kb_id: int
    file_id: int

    usage_snapshot: str
    processor_type: str

    chunk_index: int
    content: str
    char_count: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class ChunkPageResponse(BaseModel):
    items: list[ChunkResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class FileTaskSubmitResponse(BaseModel):
    file_id: int
    task_id: str
    status: str = "queued"
    message: str = ""
