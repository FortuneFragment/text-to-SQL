from __future__ import annotations

import json
import re
from typing import Any, Callable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

_FIELD_INFERENCE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "你是数据库字段语义分析助手。请根据问题、SQL、字段名和样例数据，推测每个字段的人类可读含义。\n"
            "必须返回 JSON 数组，元素结构固定为：\n"
            "[{\"column\":\"字段名\",\"inferred_meaning\":\"推测含义\",\"confidence\":0.0-1.0,\"reason\":\"简短依据\"}]\n"
            "要求：\n"
            "1. 每个输入字段都要返回一条记录。\n"
            "2. confidence 为 0~1 之间的小数。\n"
            "3. 只输出 JSON，不要 markdown，不要额外解释。"
        ),
    ),
    (
        "human",
        "用户问题：{question}\n\n"
        "执行 SQL：\n{sql}\n\n"
        "查询字段：{columns_json}\n\n"
        "样例数据（最多 5 行）：\n{sample_rows_json}\n",
    ),
])


class Text2SQLFieldInferenceService:
    def __init__(self, model_provider: Callable[[], ChatOpenAI | None]):
        self._model_provider = model_provider

    def infer_fields(
        self,
        *,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized_columns = [str(col).strip() for col in columns if str(col).strip()]
        if not normalized_columns:
            return []

        model = self._model_provider()
        if model is None:
            return self._infer_by_rules(normalized_columns, rows)

        sample_rows = self._build_sample_rows(normalized_columns, rows)
        try:
            chain = _FIELD_INFERENCE_PROMPT | model | StrOutputParser()
            raw = chain.invoke(
                {
                    "question": str(question or ""),
                    "sql": str(sql or ""),
                    "columns_json": json.dumps(normalized_columns, ensure_ascii=False),
                    "sample_rows_json": json.dumps(sample_rows, ensure_ascii=False),
                }
            )
            parsed = self._parse_llm_output(raw)
            return self._normalize_items(normalized_columns, parsed, rows)
        except Exception:  # noqa: BLE001
            return self._infer_by_rules(normalized_columns, rows)

    @staticmethod
    def _build_sample_rows(columns: list[str], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sampled: list[dict[str, Any]] = []
        for row in (rows or [])[:5]:
            entry: dict[str, Any] = {}
            for col in columns:
                if col in row:
                    entry[col] = Text2SQLFieldInferenceService._truncate_value(row.get(col))
            sampled.append(entry)
        return sampled

    @staticmethod
    def _truncate_value(value: Any, max_len: int = 80) -> Any:
        if value is None:
            return None
        text = str(value)
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    @staticmethod
    def _parse_llm_output(raw: str) -> list[dict[str, Any]]:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        payload = json.loads(text)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "fields", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _normalize_items(
        columns: list[str],
        items: list[dict[str, Any]],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        indexed = {
            str(item.get("column", "")).strip().lower(): item
            for item in (items or [])
            if str(item.get("column", "")).strip()
        }

        result: list[dict[str, Any]] = []
        for column in columns:
            key = column.lower()
            item = indexed.get(key)
            if item is None:
                result.append(Text2SQLFieldInferenceService._infer_single_by_rule(column, rows))
                continue

            meaning = str(item.get("inferred_meaning") or "").strip() or "可能是业务字段"
            reason = str(item.get("reason") or "").strip()
            confidence = Text2SQLFieldInferenceService._normalize_confidence(item.get("confidence"))
            result.append(
                {
                    "column": column,
                    "inferred_meaning": meaning,
                    "confidence": confidence,
                    "reason": reason,
                }
            )
        return result

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            num = float(value)
        except (TypeError, ValueError):
            num = 0.0
        if num < 0.0:
            num = 0.0
        if num > 1.0:
            num = 1.0
        return round(num, 2)

    @staticmethod
    def _infer_by_rules(columns: list[str], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [Text2SQLFieldInferenceService._infer_single_by_rule(column, rows) for column in columns]

    @staticmethod
    def _infer_single_by_rule(column: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        norm = column.strip().lower()
        sample_values = [row.get(column) for row in (rows or [])[:5] if column in row]
        sample_text = ", ".join(str(Text2SQLFieldInferenceService._truncate_value(v, 20)) for v in sample_values[:3])
        sample_hint = f"样例值: {sample_text}" if sample_text else "无样例值"

        if norm == "id" or norm.endswith("_id") or norm.startswith("id_"):
            return {
                "column": column,
                "inferred_meaning": "主键或关联 ID",
                "confidence": 0.55,
                "reason": f"字段名包含 id 特征。{sample_hint}",
            }

        if any(token in norm for token in ("code", "bm", "dm", "bh", "xh")):
            return {
                "column": column,
                "inferred_meaning": "业务编码字段",
                "confidence": 0.58,
                "reason": f"字段名包含 code/bm/dm/bh/xh 等编码特征。{sample_hint}",
            }

        if any(token in norm for token in ("status", "state", "zt", "flag", "is_", "sf")):
            return {
                "column": column,
                "inferred_meaning": "状态或标记字段",
                "confidence": 0.52,
                "reason": f"字段名包含状态或标记特征。{sample_hint}",
            }

        if any(token in norm for token in ("type", "kind", "lx", "lb")):
            return {
                "column": column,
                "inferred_meaning": "类型枚举字段",
                "confidence": 0.5,
                "reason": f"字段名包含类型特征。{sample_hint}",
            }

        return {
            "column": column,
            "inferred_meaning": "可能是业务字段",
            "confidence": 0.3,
            "reason": f"仅基于字段名和样例值进行弱推测。{sample_hint}",
        }
