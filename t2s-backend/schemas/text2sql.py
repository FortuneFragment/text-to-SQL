from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Text2SQLConnectionPayload(BaseModel):
    db_type: Literal["mysql"] = "mysql"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=3306, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    database: str = Field(min_length=1, max_length=255)
    charset: str = Field(default="utf8mb4", min_length=1, max_length=64)


class Text2SQLConnectionResponse(BaseModel):
    configured: bool = False
    db_type: Literal["mysql"] | None = None
    host: str = ""
    port: int = 3306
    username: str = ""
    database: str = ""
    charset: str = "utf8mb4"
    has_password: bool = False


class Text2SQLConnectionTestResponse(BaseModel):
    ok: bool
    message: str = ""


class ColumnInfo(BaseModel):
    name: str
    type: str


class TableInfo(BaseModel):
    table_name: str
    columns: list[ColumnInfo] = Field(default_factory=list)


class Text2SQLSchemaResponse(BaseModel):
    tables: list[TableInfo] = Field(default_factory=list)


class Text2SQLConfigResponse(BaseModel):
    selected_tables: list[str] = Field(default_factory=list)
    prompt_hint: str = ""


class UpdateText2SQLConfigRequest(BaseModel):
    selected_tables: list[str] = Field(default_factory=list)
    prompt_hint: str = ""


class Text2SQLQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class Text2SQLFieldInferenceItem(BaseModel):
    column: str
    inferred_meaning: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class Text2SQLQueryResponse(BaseModel):
    sql: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    answer: str
    row_count: int = 0
    repaired: bool = False
    field_inference: list[Text2SQLFieldInferenceItem] = Field(default_factory=list)


class Text2SQLDebugGenerateResponse(BaseModel):
    sql: str
    validation_passed: bool
    validation_message: str = ""


class Text2SQLQueryLogItem(BaseModel):
    id: int
    question: str
    generated_sql: str | None = None
    final_sql: str | None = None
    status: str
    error_message: str | None = None
    row_count: int | None = None
    duration_ms: int | None = None
    repaired: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
