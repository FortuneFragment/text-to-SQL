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
            "4. 明细查询建议补 LIMIT；统计聚合查询（如 COUNT/SUM/AVG）可不加 LIMIT。\n"
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
    """中文备注：封装SQL 修复。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(
        self,
        model_provider: Callable[[], ChatOpenAI | None],
        schema_service: Text2SQLSchemaService,
        ensure_limit: Callable[[str], str],
    ):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self._model_provider`。
        self._model_provider = model_provider
        self._schema_service = schema_service
        self._ensure_limit = ensure_limit

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

    def repair_sql(
        self,
        *,
        db: Session,
        question: str,
        failed_sql: str,
        error_message: str,
        runtime_config: dict[str, Any],
    ) -> str:
        """中文备注：修复sql相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `model`。
        model = self._model_provider()
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if model is None:
            return self._ensure_limit(failed_sql)

        # 3. 变量构建：计算并更新 `selected_tables`。
        selected_tables = runtime_config.get("selected_tables") or []
        queryable_columns_map = runtime_config.get("queryable_columns_map")
        schema_json = self._schema_service.build_live_schema_json(
            db,
            selected_tables or None,
            queryable_columns_map=queryable_columns_map,
        )
        allowed_tables_text = self._build_allowed_tables_text(selected_tables)
        prompt_hint = runtime_config.get("prompt_hint") or "（无）"

        # 4. 变量构建：计算并更新 `chain`。
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
        # 5. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        return self._ensure_limit(self._normalize_sql_output(repaired_sql))

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
        return sql.strip()

