from __future__ import annotations

import re
from typing import Any, Callable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from services.text2sql.schema_service import Text2SQLSchemaService

_REPAIR_SQL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "你是 SQL 修复器，请根据失败原因修复 SQL。\n\n"
            "硬性规则：\n"
            "1. 只能输出一条 SELECT 语句。\n"
            "2. 允许单表或多表 JOIN，但禁止 UNION、多语句。\n"
            "3. 表名和字段必须来自 schema_json。\n"
            "4. 如果 SQL 没有 LIMIT，必须补 LIMIT。\n"
            "5. 仅输出 SQL 本身，不要解释，不要 markdown。\n\n"
            "允许查询的表：\n{allowed_tables_text}\n\n"
            "真实数据库结构（JSON）：\n{schema_json}\n\n"
            "额外业务约束：\n{prompt_hint}\n"
        ),
    ),
    (
        "human",
        "用户问题：{question}\n\n"
        "失败 SQL：\n{failed_sql}\n\n"
        "错误原因：{error_message}\n",
    ),
])


class Text2SQLRepairService:
    def __init__(
        self,
        model_provider: Callable[[], ChatOpenAI | None],
        schema_service: Text2SQLSchemaService,
        ensure_limit: Callable[[str], str],
    ):
        self._model_provider = model_provider
        self._schema_service = schema_service
        self._ensure_limit = ensure_limit

    @staticmethod
    def _build_allowed_tables_text(selected_tables: list[str]) -> str:
        if not selected_tables:
            return "（未指定；可从 schema_json 中选择一张表）"
        return "\n".join(f"- {table_name}" for table_name in selected_tables)

    def repair_sql(
        self,
        *,
        db: Session,
        question: str,
        failed_sql: str,
        error_message: str,
        runtime_config: dict[str, Any],
    ) -> str:
        model = self._model_provider()
        if model is None:
            return self._ensure_limit(failed_sql)

        selected_tables = runtime_config.get("selected_tables") or []
        schema_json = self._schema_service.build_live_schema_json(db, selected_tables or None)
        allowed_tables_text = self._build_allowed_tables_text(selected_tables)
        prompt_hint = runtime_config.get("prompt_hint") or "（无）"

        chain = _REPAIR_SQL_PROMPT | model | StrOutputParser()
        repaired_sql = chain.invoke(
            {
                "question": question,
                "failed_sql": failed_sql,
                "error_message": error_message,
                "allowed_tables_text": allowed_tables_text,
                "schema_json": schema_json,
                "prompt_hint": prompt_hint,
            }
        )
        return self._ensure_limit(self._normalize_sql_output(repaired_sql))

    @staticmethod
    def _normalize_sql_output(raw_sql: str) -> str:
        sql = raw_sql.strip()
        if sql.startswith("```"):
            sql = re.sub(r"^```\w*\n?", "", sql)
            sql = re.sub(r"\n?```$", "", sql)
        return sql.strip()

