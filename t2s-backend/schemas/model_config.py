from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

ModelKind = Literal["llm", "embedding", "rerank"]
SUPPORTED_PROVIDERS = [
    "openai",
    "dashscope",
    "zhipu",
    "baichuan",
    "moonshot",
    "deepseek",
    "ollama",
    "azure_openai",
    "anthropic",
    "cohere",
    "jina",
    "local",
    "custom",
]
SUPPORTED_MODEL_TYPES = ["llm", "embedding", "rerank"]


class ModelConfigCreateRequest(BaseModel):
    kind: ModelKind = Field(validation_alias=AliasChoices("kind", "model_type"))
    name: str = Field(min_length=1, max_length=128)
    provider: str = Field(default="custom", min_length=1, max_length=64)
    base_url: str = Field(min_length=1, max_length=1024, validation_alias=AliasChoices("base_url", "api_base_url"))
    model_name: str = Field(min_length=1, max_length=255)
    api_key: str | None = Field(default=None, max_length=2048)
    extra_params: str | None = Field(default=None)

    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    vector_dim: int | None = Field(default=None, ge=1, le=65536)
    batch_size: int | None = Field(default=None, ge=1, le=2048)
    verify_ssl: bool = True
    ca_bundle: str | None = Field(default=None, max_length=4096)
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=0.5, ge=0.0, le=60.0)
    trust_env: bool = True
    is_active: bool = False
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_embedding_fields(self) -> "ModelConfigCreateRequest":
        if self.kind == "embedding" and not self.batch_size:
            self.batch_size = 32
        return self

    @property
    def model_type(self) -> str:
        return self.kind

    @property
    def api_base_url(self) -> str:
        return self.base_url


class ModelConfigUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = Field(default=None, min_length=1, max_length=1024, validation_alias=AliasChoices("base_url", "api_base_url"))
    model_name: str | None = Field(default=None, min_length=1, max_length=255)
    api_key: str | None = Field(default=None, max_length=2048)
    extra_params: str | None = Field(default=None)

    timeout_seconds: int | None = Field(default=None, ge=1, le=3600)
    vector_dim: int | None = Field(default=None, ge=1, le=65536)
    batch_size: int | None = Field(default=None, ge=1, le=2048)
    verify_ssl: bool | None = None
    ca_bundle: str | None = Field(default=None, max_length=4096)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    retry_backoff_seconds: float | None = Field(default=None, ge=0.0, le=60.0)
    trust_env: bool | None = None
    is_active: bool | None = None
    model_config = ConfigDict(populate_by_name=True)

    @property
    def api_base_url(self) -> str | None:
        return self.base_url


class ModelConfigResponse(BaseModel):
    id: int
    kind: str
    model_type: str
    name: str
    provider: str
    base_url: str
    api_base_url: str
    model_name: str
    has_api_key: bool = False
    api_key_masked: str = ""
    extra_params: str | None = None

    timeout_seconds: int
    vector_dim: int | None = None
    batch_size: int | None = None
    verify_ssl: bool
    ca_bundle: str | None = None
    max_retries: int
    retry_backoff_seconds: float
    trust_env: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelConfigListResponse(BaseModel):
    items: list[ModelConfigResponse] = Field(default_factory=list)


class ModelConfigActivationResponse(BaseModel):
    config: ModelConfigResponse
    warning: str | None = None
    needs_rebuild: bool = False


class ModelProviderInfo(BaseModel):
    provider: str
    display_name: str
    supported_types: list[str] = Field(default_factory=list)


class ModelProviderListResponse(BaseModel):
    items: list[ModelProviderInfo] = Field(default_factory=list)
