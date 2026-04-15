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
            "5. 明细查询建议补 LIMIT；统计聚合查询（如 COUNT/SUM/AVG）可不加 LIMIT。\n"
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
    """中文备注：封装SQL 生成。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(
        self,
        model_provider: Callable[[], ChatOpenAI | None],
        schema_service: Text2SQLSchemaService,
    ):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self._model_provider`。
        self._model_provider = model_provider
        self._schema_service = schema_service

    @staticmethod
    def _build_allowed_tables_text(selected_tables: list[str]) -> str:
        """中文备注：构建allowed tables text相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if not selected_tables:
            return "（未指定；可从 schema_json 中选择一张表）"
        # 2. 返回结果：输出当前函数最终结果。
        return "\n".join(f"- {table_name}" for table_name in selected_tables)

    def generate_sql(
        self,
        *,
        db: Session,
        question: str,
        runtime_config: dict[str, Any],
    ) -> str:
        """中文备注：处理sql相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `selected_tables`。
        selected_tables = runtime_config.get("selected_tables") or []
        prompt_hint = runtime_config.get("prompt_hint") or "（无）"
        queryable_columns_map = runtime_config.get("queryable_columns_map")

        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not selected_tables:
            raise ValueError("未选择可查询的表，无法生成 SQL")

        # 3. 变量构建：计算并更新 `model`。
        model = self._model_provider()
        candidate_table = selected_tables[0]
        # 4. 条件分支：根据当前状态选择不同处理路径。
        if model is None:
            return f"SELECT * FROM {candidate_table} LIMIT {settings.TEXT2SQL_MAX_ROWS};"

        # 5. 变量构建：计算并更新 `schema_json`。
        schema_json = self._schema_service.build_live_schema_json(
            db,
            selected_tables,
            queryable_columns_map=queryable_columns_map,
        )
        chain = _GENERATE_SQL_PROMPT | model | StrOutputParser()
        raw_sql = chain.invoke(
            {
                "question": question,
                "schema_json": schema_json,
                "allowed_tables_text": self._build_allowed_tables_text(selected_tables),
                "prompt_hint": prompt_hint,
            }
        )
        # 6. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        return self._normalize_sql_output(raw_sql)

    @staticmethod
    def _normalize_sql_output(raw_sql: str) -> str:
        """中文备注：规范化sql output相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `sql`。
        sql = raw_sql.strip()
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if sql.startswith("```"):
            sql = re.sub(r"^```\w*\n?", "", sql)
            sql = re.sub(r"\n?```$", "", sql)
        # 3. 返回结果：输出当前函数最终结果。
        return sql.strip().rstrip(";") + ";"

