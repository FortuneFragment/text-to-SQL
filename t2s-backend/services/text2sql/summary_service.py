from __future__ import annotations

from typing import Any, Callable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

_SUMMARIZE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "你是数据分析助手。用户通过自然语言提问，系统已从数据库查到结果。\n"
        "请用清晰、友好的中文总结查询结果，可以适当使用表格或列表格式。\n"
        "如果结果为空，说明未查到符合条件的数据。",
    ),
    ("human", "用户问题：{question}\n\n执行的SQL：\n{sql}\n\n查询结果：\n{result_text}"),
])


class Text2SQLSummaryService:
    """中文备注：封装结果总结。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(self, model_provider: Callable[[], ChatOpenAI | None]):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self._model_provider`。
        self._model_provider = model_provider

    def summarize_result(
        self,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> str:
        """中文备注：处理result相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `model`。
        model = self._model_provider()
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if model is None:
            return self.build_fallback_summary(columns, rows)

        # 3. 变量构建：计算并更新 `result_text`。
        result_text = self.format_result_text(columns, rows)
        chain = _SUMMARIZE_PROMPT | model | StrOutputParser()
        # 4. 返回结果：输出当前函数最终结果。
        return chain.invoke(
            {
                "question": question,
                "sql": sql,
                "result_text": result_text,
            }
        )

    @staticmethod
    def build_fallback_summary(columns: list[str], rows: list[dict[str, Any]]) -> str:
        """中文备注：构建fallback summary相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if not rows:
            return "未查到符合条件的数据。"

        # 2. 变量构建：计算并更新 `total_rows`。
        total_rows = len(rows)
        total_columns = len(columns)
        # 3. 条件分支：根据当前状态选择不同处理路径。
        if total_rows == 1 and total_columns == 1:
            only_column = columns[0]
            return f"查询完成，共 1 条结果：{only_column} = {rows[0].get(only_column, '')}"

        # 4. 变量构建：计算并更新 `visible_columns`。
        visible_columns = "、".join(columns[:6])
        # 5. 条件分支：根据当前状态选择不同处理路径。
        if total_columns > 6:
            visible_columns += " 等"
        # 6. 返回结果：输出当前函数最终结果。
        return (
            f"查询完成，共返回 {total_rows} 行、{total_columns} 列。"
            f"字段包括：{visible_columns}。"
            "下方表格可查看明细数据。"
        )

    @staticmethod
    def format_result_text(columns: list[str], rows: list[dict[str, Any]]) -> str:
        """中文备注：格式化result text相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if not rows:
            return "查询结果为空，没有符合条件的数据。"

        # 2. 变量构建：计算并更新 `header`。
        header = " | ".join(columns)
        lines = [header, "-" * len(header)]
        # 3. 迭代处理：遍历集合并逐项构建结果。
        for row in rows[:50]:
            lines.append(" | ".join(str(row.get(column, "")) for column in columns))
        # 4. 条件分支：根据当前状态选择不同处理路径。
        if len(rows) > 50:
            lines.append(f"... 共 {len(rows)} 行，仅展示前 50 行")
        # 5. 返回结果：输出当前函数最终结果。
        return "\n".join(lines)
