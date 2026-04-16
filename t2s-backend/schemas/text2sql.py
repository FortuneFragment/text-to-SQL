from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Text2SQLConnectionPayload(BaseModel):
    """中文备注：封装连接管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    db_type: Literal["mysql"] = "mysql"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=3306, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    database: str = Field(min_length=1, max_length=255)
    charset: str = Field(default="utf8mb4", min_length=1, max_length=64)


class Text2SQLConnectionResponse(BaseModel):
    """中文备注：封装连接管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    configured: bool = False
    db_type: Literal["mysql"] | None = None
    host: str = ""
    port: int = 3306
    username: str = ""
    database: str = ""
    charset: str = "utf8mb4"
    has_password: bool = False


class Text2SQLConnectionTestResponse(BaseModel):
    """中文备注：封装连接管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    ok: bool
    message: str = ""


class ColumnInfo(BaseModel):
    """中文备注：封装ColumnInfo相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    name: str
    type: str
    comment: str = ""


class TableInfo(BaseModel):
    """中文备注：封装TableInfo相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    table_name: str
    table_comment: str = ""
    columns: list[ColumnInfo] = Field(default_factory=list)


class Text2SQLSchemaResponse(BaseModel):
    """中文备注：封装Schema 信息处理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    tables: list[TableInfo] = Field(default_factory=list)


class Text2SQLTableOption(BaseModel):
    """中文备注：封装Text2SQLTableOption相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    table_name: str
    table_comment: str = ""


class Text2SQLTableOptionsResponse(BaseModel):
    """中文备注：封装Text2SQLTableOptionsResponse相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    tables: list[Text2SQLTableOption] = Field(default_factory=list)


class Text2SQLTableFieldItem(BaseModel):
    """中文备注：封装Text2SQLTableFieldItem相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    name: str
    type: str
    comment: str = ""
    query_enabled: bool = True


class Text2SQLTableFieldsResponse(BaseModel):
    """中文备注：封装Text2SQLTableFieldsResponse相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    table_name: str
    table_comment: str = ""
    fields: list[Text2SQLTableFieldItem] = Field(default_factory=list)


class Text2SQLConfigResponse(BaseModel):
    """中文备注：封装配置管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    selected_tables: list[str] = Field(default_factory=list)
    prompt_hint: str = ""


class UpdateText2SQLConfigRequest(BaseModel):
    """中文备注：封装配置管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    selected_tables: list[str] = Field(default_factory=list)
    prompt_hint: str = ""


class UpdateText2SQLTableFieldItem(BaseModel):
    """中文备注：封装UpdateText2SQLTableFieldItem相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    name: str = Field(min_length=1, max_length=255)
    query_enabled: bool = True


class UpdateText2SQLTableFieldsRequest(BaseModel):
    """中文备注：封装UpdateText2SQLTableFieldsRequest相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    fields: list[UpdateText2SQLTableFieldItem] = Field(default_factory=list, min_length=1)


class Text2SQLQueryRequest(BaseModel):
    """中文备注：封装Text2SQLQueryRequest相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    question: str = Field(min_length=1, max_length=4000)


class Text2SQLFieldInferenceItem(BaseModel):
    """中文备注：封装Text2SQLFieldInferenceItem相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    column: str
    inferred_meaning: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    table_name: str = ""
    table_comment: str = ""
    column_name: str = ""
    column_comment: str = ""


class Text2SQLQueryResponse(BaseModel):
    """中文备注：封装Text2SQLQueryResponse相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    sql: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    answer: str
    row_count: int = 0
    repaired: bool = False
    field_inference: list[Text2SQLFieldInferenceItem] = Field(default_factory=list)


class Text2SQLDebugGenerateResponse(BaseModel):
    """中文备注：封装Text2SQLDebugGenerateResponse相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    sql: str
    validation_passed: bool
    validation_message: str = ""


class Text2SQLQueryLogItem(BaseModel):
    """中文备注：封装Text2SQLQueryLogItem相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
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
