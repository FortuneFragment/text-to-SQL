"""Text2SQL 结果摘要服务。

把执行得到的结果集（列 + 行）连同原始问题与 SQL 交给大模型，生成清晰友好的中文回答，
支持一次性与流式两种输出；模型不可用或流式失败时，降级为基于行列统计的兜底文案，
保证「即使没有大模型也能给用户一个可读的结果说明」。
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Callable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

_SUMMARIZE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "你是数据分析助手。用户通过自然语言提问，系统已从数据库查到结果。\n"
        "请只用自然语言中文总结查询结果，不要输出 Markdown 表格、HTML 表格、代码块或竖线分隔表格。\n"
        "总结必须覆盖查询结果中的字段信息，不要省略 SQL 已返回的字段。\n"
        "如果结果中有 null、None 或空值，要用中文说明哪些字段存在空值，不要把 null 当成普通文本直接罗列。\n"
        "如果结果为空，说明未查到符合条件的数据。",
    ),
    ("human", "用户问题：{question}\n\n执行的SQL：\n{sql}\n\n查询结果：\n{result_text}"),
])

class Text2SQLSummaryService:
    """把 SQL 结果整理成面向用户的自然语言总结。"""
    def __init__(
        self,
        model_provider: Callable[[], ChatOpenAI | None],
        streaming_model_provider: Callable[[], ChatOpenAI | None] | None = None,
    ):
        """注入模型提供器。"""
        self._model_provider = model_provider
        self._streaming_model_provider = streaming_model_provider or model_provider

    def summarize_result(
        self,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> str:
        """生成查询结果摘要；模型不可用时使用兜底文案。"""
        model = self._model_provider()
        if model is None:
            return self.build_fallback_summary(columns, rows)
        result_text = self.format_result_text(columns, rows)
        chain = _SUMMARIZE_PROMPT | model | StrOutputParser()
        return chain.invoke(
            {
                "question": question,
                "sql": sql,
                "result_text": result_text,
            }
        )

    def stream_summarize_result(
        self,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> Generator[str, None, None]:
        """流式生成查询结果摘要；失败时降级为一次性摘要。"""
        model = self._streaming_model_provider()
        if model is None:
            yield from self._iter_text_chunks(self.build_fallback_summary(columns, rows))
            return

        result_text = self.format_result_text(columns, rows)
        chain = _SUMMARIZE_PROMPT | model | StrOutputParser()
        has_content = False

        try:
            for chunk in chain.stream(
                {
                    "question": question,
                    "sql": sql,
                    "result_text": result_text,
                }
            ):
                if chunk:
                    has_content = True
                    yield chunk
        except Exception:  # noqa: BLE001
            has_content = False

        if not has_content:
            try:
                yield from self._iter_text_chunks(self.summarize_result(question, sql, columns, rows))
            except Exception:  # noqa: BLE001
                yield from self._iter_text_chunks(self.build_fallback_summary(columns, rows))

    @staticmethod
    def _iter_text_chunks(text: str, chunk_size: int = 24) -> Generator[str, None, None]:
        """把兜底摘要也按小段推给前端，保持 SSE 消费侧行为一致。"""
        safe_text = str(text or "")
        if not safe_text:
            return
        safe_chunk_size = max(1, int(chunk_size or 1))
        for start in range(0, len(safe_text), safe_chunk_size):
            yield safe_text[start : start + safe_chunk_size]

    @staticmethod
    def build_fallback_summary(columns: list[str], rows: list[dict[str, Any]]) -> str:
        """在无模型场景下生成简明中文摘要。"""
        if not rows:
            return "未查到符合条件的数据。"
        total_rows = len(rows)
        total_columns = len(columns)
        null_summary = Text2SQLSummaryService.build_null_summary(columns, rows)
        if total_rows == 1 and total_columns == 1:
            only_column = columns[0]
            value_text = Text2SQLSummaryService.format_value_for_summary(rows[0].get(only_column))
            sentence = f"查询完成，共 1 条结果，字段 {only_column} 的值为 {value_text}。"
            return f"{sentence}{null_summary}" if null_summary else sentence
        fields_text = "、".join(str(column) for column in columns)
        sentence = f"查询完成，共返回 {total_rows} 行、{total_columns} 列，字段包括：{fields_text}。"
        return f"{sentence}{null_summary}" if null_summary else sentence

    @staticmethod
    def is_null_like(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in {"null", "none"}
        return False

    @staticmethod
    def format_value_for_summary(value: Any) -> str:
        if Text2SQLSummaryService.is_null_like(value):
            return "空值"
        text = str(value)
        return text if text else "空字符串"

    @staticmethod
    def build_null_summary(columns: list[str], rows: list[dict[str, Any]]) -> str:
        null_counts: dict[str, int] = {}
        for row in rows:
            for column in columns:
                if Text2SQLSummaryService.is_null_like(row.get(column)):
                    null_counts[column] = null_counts.get(column, 0) + 1
        if not null_counts:
            return ""
        parts = [f"{column} 有 {count} 条为空值" for column, count in null_counts.items()]
        return " 其中，" + "；".join(parts) + "。"

    @staticmethod
    def format_result_text(columns: list[str], rows: list[dict[str, Any]]) -> str:
        """把结果集格式化成适合喂给模型的文本。"""
        if not rows:
            return "查询结果为空，没有符合条件的数据。"
        lines = [
            f"查询结果共 {len(rows)} 行，字段包括：{'、'.join(str(column) for column in columns)}。"
        ]
        null_summary = Text2SQLSummaryService.build_null_summary(columns, rows)
        if null_summary:
            lines.append(null_summary.strip())
        for index, row in enumerate(rows[:50], start=1):
            field_parts = [
                f"{column} 为 {Text2SQLSummaryService.format_value_for_summary(row.get(column))}"
                for column in columns
            ]
            lines.append(f"第 {index} 行：" + "；".join(field_parts) + "。")
        if len(rows) > 50:
            lines.append(f"... 共 {len(rows)} 行，仅展示前 50 行")
        return "\n".join(lines)
