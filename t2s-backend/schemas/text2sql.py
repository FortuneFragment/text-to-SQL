"""Text2SQL 接口请求/响应数据模型（Pydantic Schema）。

定义对外 API 的入参与出参契约，覆盖连接配置、表/字段结构与权限、表关系、问答查询、
调试生成、查询日志等。约定：响应模型一律不含明文密码；带 from_attributes 的模型可直接由
ORM 实体转换。这里只做数据形状与字段校验（长度/范围/枚举），业务逻辑在 services 层。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Text2SQLConnectionPayload(BaseModel):
    """前端提交的数据库连接参数（业务库当前仅支持 SQL Server）。"""

    db_type: Literal["sqlserver"] = "sqlserver"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=1433, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    database: str = Field(min_length=1, max_length=255)
    # 选定的数据库架构（schema），如 dbo；留空表示用连接默认架构。
    db_schema: str | None = Field(default=None, max_length=128)
    charset: str = Field(default="UTF-8", min_length=1, max_length=64)


class Text2SQLConnectionResponse(BaseModel):
    """返回给前端的连接配置（不包含明文密码）。"""

    configured: bool = False
    db_type: Literal["sqlserver"] | None = None
    host: str = ""
    port: int = 1433
    username: str = ""
    database: str = ""
    db_schema: str = ""
    charset: str = "UTF-8"
    has_password: bool = False


class Text2SQLConnectionTestResponse(BaseModel):
    """连接测试接口的返回结构。"""

    ok: bool
    message: str = ""


class Text2SQLSchemaNamesResponse(BaseModel):
    """业务库可选「架构（schema）」列表，供前端连接配置选择。"""

    schemas: list[str] = Field(default_factory=list)


class ColumnInfo(BaseModel):
    """单个字段的基础信息。"""

    name: str
    type: str
    comment: str = ""
    aliases: list[str] = Field(default_factory=list)


class TableInfo(BaseModel):
    """单张表的结构信息。"""

    table_name: str
    table_comment: str = ""
    columns: list[ColumnInfo] = Field(default_factory=list)


class Text2SQLSchemaResponse(BaseModel):
    """数据库 Schema 概览响应。"""

    tables: list[TableInfo] = Field(default_factory=list)


class Text2SQLTableOption(BaseModel):
    """数据表选项。"""

    table_name: str
    table_comment: str = ""


class Text2SQLTableOptionsResponse(BaseModel):
    """数据表列表响应。"""

    tables: list[Text2SQLTableOption] = Field(default_factory=list)


class Text2SQLConfigResponse(BaseModel):
    """当前连接对应的配置响应。"""

    prompt_hint: str = ""


class UpdateText2SQLConfigRequest(BaseModel):
    """更新提示词时的请求体。"""

    prompt_hint: str = ""


class Text2SQLRelationUpsertRequest(BaseModel):
    """新增/更新表关系的请求体（支持复合键）。"""

    source_table: str = Field(min_length=1, max_length=64)
    source_columns: list[str] = Field(default_factory=list, min_length=1)
    target_table: str = Field(min_length=1, max_length=64)
    target_columns: list[str] = Field(default_factory=list, min_length=1)
    relation_type: str = Field(default="N:1", max_length=16)
    description: str = ""


class CreateText2SQLRelationRequest(Text2SQLRelationUpsertRequest):
    """新增关系请求。"""


class UpdateText2SQLRelationRequest(Text2SQLRelationUpsertRequest):
    """更新关系请求。"""


class BatchImportText2SQLRelationsRequest(BaseModel):
    """批量导入关系请求（overwrite_existing 控制命中已有关系时覆盖还是跳过）。"""

    relations: list[CreateText2SQLRelationRequest] = Field(default_factory=list, min_length=1)
    overwrite_existing: bool = False


class Text2SQLRelationItem(BaseModel):
    """关系配置条目。"""

    id: int
    source_table: str
    source_columns: list[str] = Field(default_factory=list)
    target_table: str
    target_columns: list[str] = Field(default_factory=list)
    relation_type: str = ""
    description: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Text2SQLRelationListResponse(BaseModel):
    """关系列表分页响应。"""

    items: list[Text2SQLRelationItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class Text2SQLRelationBatchImportResponse(BaseModel):
    """批量导入结果统计（总数 / 新增 / 更新 / 跳过 / 失败 + 错误明细）。"""

    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class Text2SQLRelationTableColumnsResponse(BaseModel):
    """关系配置时读取表字段列表的响应。"""

    table_name: str
    table_comment: str = ""
    columns: list[ColumnInfo] = Field(default_factory=list)


class Text2SQLTurn(BaseModel):
    """多轮对话中的单轮历史（前端持有并随每次请求回传）。"""

    question: str = Field(default="", max_length=4000)
    sql: str = Field(default="", max_length=8000)
    answer: str = Field(default="", max_length=4000)


class Text2SQLQueryRequest(BaseModel):
    """自然语言问答请求体。"""

    question: str = Field(min_length=1, max_length=4000)
    history: list[Text2SQLTurn] = Field(default_factory=list, max_length=20)


class Text2SQLFieldInferenceItem(BaseModel):
    """查询结果字段与数据库注释的绑定信息。"""

    column: str
    inferred_meaning: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    table_name: str = ""
    table_comment: str = ""
    column_name: str = ""
    column_comment: str = ""


class Text2SQLQueryResponse(BaseModel):
    """问答接口返回的 SQL、数据和总结。"""

    sql: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    decoded_rows: list[dict[str, Any]] = Field(default_factory=list)
    answer: str
    row_count: int = 0
    repaired: bool = False
    field_inference: list[Text2SQLFieldInferenceItem] = Field(default_factory=list)
    # 本次查询对应的日志 id；前端凭此提交满意度评分（用于 few-shot 示例晋升）。
    log_id: int | None = None
    # 非空时表示路由信号不足、需要用户补充澄清；此时不会生成/执行 SQL。
    clarification: str = ""


class Text2SQLFeedbackRequest(BaseModel):
    """用户对某条查询结果的满意度评分请求（1-5 星）。"""

    log_id: int = Field(ge=1)
    score: int = Field(ge=1, le=5)
    question: str | None = Field(default=None, max_length=4000)
    sql: str | None = Field(default=None, max_length=8000)
    answer: str | None = Field(default=None, max_length=8000)
    selected_tables: list[str] = Field(default_factory=list, max_length=50)


class Text2SQLDebugGenerateResponse(BaseModel):
    """调试接口返回的 SQL 生成与校验信息。"""

    sql: str
    validation_passed: bool
    validation_message: str = ""
    route_mode: str = ""
    route_tables: list[str] = Field(default_factory=list)
    route_pool_tables: list[str] = Field(default_factory=list)
    route_scores: dict[str, float] = Field(default_factory=dict)
    relation_hints: list[str] = Field(default_factory=list)
    relation_guard_used: bool = False


class SchemaAnnotationImportSampleItem(BaseModel):
    table_name: str
    column_name: str
    table_comment: str | None = None
    column_comment: str | None = None
    aliases: list[str] = Field(default_factory=list)


class SchemaAnnotationImportResponse(BaseModel):
    connection_key: str
    parsed: int = 0
    upserted: int = 0
    skipped: int = 0
    sample: list[SchemaAnnotationImportSampleItem] = Field(default_factory=list)


class CodeDictValueReport(BaseModel):
    value_count: int = 0
    category_count: int = 0
    written: int = 0
    skipped_rows: int = 0


class CodeDictBindingReport(BaseModel):
    binding_count: int = 0
    written: int = 0
    skipped_rows: int = 0


class CodeDictImportResponse(BaseModel):
    connection_key: str
    value: CodeDictValueReport = Field(default_factory=CodeDictValueReport)
    binding: CodeDictBindingReport = Field(default_factory=CodeDictBindingReport)
    ignored_files: list[str] = Field(default_factory=list)


class Text2SQLQueryLogItem(BaseModel):
    """查询日志列表中的单条记录。"""

    id: int
    question: str
    generated_sql: str | None = None
    final_sql: str | None = None
    status: str
    error_message: str | None = None
    relation_guard_used: bool = False
    row_count: int | None = None
    duration_ms: int | None = None
    repaired: bool
    feedback_score: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
