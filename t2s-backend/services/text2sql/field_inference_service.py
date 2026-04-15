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
    """中文备注：封装服务层能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(self, model_provider: Callable[[], ChatOpenAI | None]):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self._model_provider`。
        self._model_provider = model_provider

    def infer_fields(
        self,
        *,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """中文备注：推断fields相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        normalized_columns = [str(col).strip() for col in columns if str(col).strip()]
        # 2. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        if not normalized_columns:
            return []

        # 3. 变量构建：计算并更新 `model`。
        model = self._model_provider()
        # 4. 条件分支：根据当前状态选择不同处理路径。
        if model is None:
            return self._infer_by_rules(normalized_columns, rows)

        # 5. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        sample_rows = self._build_sample_rows(normalized_columns, rows)
        # 6. 核心处理：执行当前阶段的业务逻辑。
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
        """中文备注：构建sample rows相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `sampled: list[dict[str, Any]]`。
        sampled: list[dict[str, Any]] = []
        # 2. 迭代处理：遍历集合并逐项构建结果。
        for row in (rows or [])[:5]:
            entry: dict[str, Any] = {}
            for col in columns:
                if col in row:
                    entry[col] = Text2SQLFieldInferenceService._truncate_value(row.get(col))
            sampled.append(entry)
        # 3. 返回结果：输出当前函数最终结果。
        return sampled

    @staticmethod
    def _truncate_value(value: Any, max_len: int = 80) -> Any:
        """中文备注：截断value相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if value is None:
            return None
        text = str(value)
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if len(text) <= max_len:
            return text
        # 3. 返回结果：输出当前函数最终结果。
        return text[: max_len - 3] + "..."

    @staticmethod
    def _parse_llm_output(raw: str) -> list[dict[str, Any]]:
        """中文备注：解析llm output相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `text`。
        text = str(raw or "").strip()
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        # 3. 结果组装：将当前阶段产物写入结构化结果。
        payload = json.loads(text)
        # 4. 条件分支：根据当前状态选择不同处理路径。
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        # 5. 条件分支：根据当前状态选择不同处理路径。
        if isinstance(payload, dict):
            for key in ("items", "fields", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        # 6. 返回结果：输出当前函数最终结果。
        return []

    @staticmethod
    def _normalize_items(
        columns: list[str],
        items: list[dict[str, Any]],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """中文备注：规范化items相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `indexed`。
        indexed = {
            str(item.get("column", "")).strip().lower(): item
            for item in (items or [])
            if str(item.get("column", "")).strip()
        }

        # 2. 变量构建：计算并更新 `result: list[dict[str, Any]]`。
        result: list[dict[str, Any]] = []
        # 3. 迭代处理：遍历集合并逐项构建结果。
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
        # 4. 返回结果：输出当前函数最终结果。
        return result

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        """中文备注：规范化confidence相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 核心处理：执行当前阶段的业务逻辑。
        try:
            num = float(value)
        except (TypeError, ValueError):
            num = 0.0
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if num < 0.0:
            num = 0.0
        # 3. 条件分支：根据当前状态选择不同处理路径。
        if num > 1.0:
            num = 1.0
        # 4. 返回结果：输出当前函数最终结果。
        return round(num, 2)

    @staticmethod
    def _infer_by_rules(columns: list[str], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """中文备注：推断by rules相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return [Text2SQLFieldInferenceService._infer_single_by_rule(column, rows) for column in columns]

    @staticmethod
    def _infer_single_by_rule(column: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """中文备注：推断single by rule相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `norm`。
        norm = column.strip().lower()
        sample_values = [row.get(column) for row in (rows or [])[:5] if column in row]
        sample_text = ", ".join(str(Text2SQLFieldInferenceService._truncate_value(v, 20)) for v in sample_values[:3])
        sample_hint = f"样例值: {sample_text}" if sample_text else "无样例值"

        # 2. 条件分支：根据当前状态选择不同处理路径。
        if norm == "id" or norm.endswith("_id") or norm.startswith("id_"):
            return {
                "column": column,
                "inferred_meaning": "主键或关联 ID",
                "confidence": 0.55,
                "reason": f"字段名包含 id 特征。{sample_hint}",
            }

        # 3. 条件分支：根据当前状态选择不同处理路径。
        if any(token in norm for token in ("code", "bm", "dm", "bh", "xh")):
            return {
                "column": column,
                "inferred_meaning": "业务编码字段",
                "confidence": 0.58,
                "reason": f"字段名包含 code/bm/dm/bh/xh 等编码特征。{sample_hint}",
            }

        # 4. 条件分支：根据当前状态选择不同处理路径。
        if any(token in norm for token in ("status", "state", "zt", "flag", "is_", "sf")):
            return {
                "column": column,
                "inferred_meaning": "状态或标记字段",
                "confidence": 0.52,
                "reason": f"字段名包含状态或标记特征。{sample_hint}",
            }

        # 5. 条件分支：根据当前状态选择不同处理路径。
        if any(token in norm for token in ("type", "kind", "lx", "lb")):
            return {
                "column": column,
                "inferred_meaning": "类型枚举字段",
                "confidence": 0.5,
                "reason": f"字段名包含类型特征。{sample_hint}",
            }

        # 6. 返回结果：输出当前函数最终结果。
        return {
            "column": column,
            "inferred_meaning": "可能是业务字段",
            "confidence": 0.3,
            "reason": f"仅基于字段名和样例值进行弱推测。{sample_hint}",
        }
