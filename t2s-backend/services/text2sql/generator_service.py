from __future__ import annotations

import re
from typing import Any, Callable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from core.config import settings
from services.text2sql.schema_service import Text2SQLSchemaService

_GENERATE_SQL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "你是一个严格的 SQL 生成器，必须基于真实数据库结构输出查询语句。\n\n"
            "硬性规则：\n"
            "1. 只能输出一条 SELECT 语句。\n"
            "2. 允许单表或多表 JOIN，但禁止 UNION、多语句。\n"
            "3. 表名和字段必须来自 schema_json，禁止臆造。\n"
            "4. 当问题信息不足时，优先忽略无法确认的条件，不要猜字段。\n"
            "5. 如果 SQL 没有 LIMIT，必须补 LIMIT。\n"
            "6. 仅输出 SQL 本身，不要解释，不要 markdown。\n\n"
            "7. 若用户问“有哪些/列表/明细”，优先返回可读的关键字段，不要只返回单个编码类字段。\n\n"
            "允许查询的表：\n{allowed_tables_text}\n\n"
            "真实数据库结构（JSON）：\n{schema_json}\n\n"
            "额外业务约束：\n{prompt_hint}\n"
        ),
    ),
    ("human", "用户问题：{question}"),
])


class Text2SQLGeneratorService:
    def __init__(
        self,
        model_provider: Callable[[], ChatOpenAI | None],
        schema_service: Text2SQLSchemaService,
    ):
        self._model_provider = model_provider
        self._schema_service = schema_service

    @staticmethod
    def _build_allowed_tables_text(selected_tables: list[str]) -> str:
        if not selected_tables:
            return "（未指定；可从 schema_json 中选择一张表）"
        return "\n".join(f"- {table_name}" for table_name in selected_tables)

    def generate_sql(
        self,
        *,
        db: Session,
        question: str,
        runtime_config: dict[str, Any],
    ) -> str:
        selected_tables = runtime_config.get("selected_tables") or []
        prompt_hint = runtime_config.get("prompt_hint") or "（无）"

        if not selected_tables:
            raise ValueError("未选择可查询的表，无法生成 SQL")

        model = self._model_provider()
        candidate_table = selected_tables[0]
        if model is None:
            return f"SELECT * FROM {candidate_table} LIMIT {settings.TEXT2SQL_MAX_ROWS};"

        schema_json = self._schema_service.build_live_schema_json(db, selected_tables)
        chain = _GENERATE_SQL_PROMPT | model | StrOutputParser()
        raw_sql = chain.invoke(
            {
                "question": question,
                "schema_json": schema_json,
                "allowed_tables_text": self._build_allowed_tables_text(selected_tables),
                "prompt_hint": prompt_hint,
            }
        )
        return self._normalize_sql_output(raw_sql)

    @staticmethod
    def _normalize_sql_output(raw_sql: str) -> str:
        sql = raw_sql.strip()
        if sql.startswith("```"):
            sql = re.sub(r"^```\w*\n?", "", sql)
            sql = re.sub(r"\n?```$", "", sql)
        return sql.strip().rstrip(";") + ";"

