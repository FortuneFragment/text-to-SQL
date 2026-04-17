from __future__ import annotations

import json
from typing import Iterable

from sqlalchemy.orm import Session

from models.text2sql_query_log import Text2SQLQueryLog
from services.embeddings import get_embeddings


class Text2SQLFewShotService:
    """从历史成功日志中检索相似问答，构建动态 Few-Shot 片段。"""

    def __init__(self, max_examples: int = 3, candidate_limit: int = 200) -> None:
        self._max_examples = max(1, int(max_examples))
        self._candidate_limit = max(1, int(candidate_limit))

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        text = (value or "").strip().strip("`").strip('"')
        if "." in text:
            text = text.split(".")[-1]
        return text.lower()

    @classmethod
    def _parse_selected_tables(cls, raw_value: str | None) -> set[str]:
        if not raw_value:
            return set()
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return set()
        if not isinstance(parsed, list):
            return set()
        normalized_tables: set[str] = set()
        for item in parsed:
            normalized = cls._normalize_identifier(str(item or ""))
            if normalized:
                normalized_tables.add(normalized)
        return normalized_tables

    @staticmethod
    def _safe_vector(values: Iterable[float] | None) -> list[float]:
        if values is None:
            return []
        try:
            return [float(item) for item in values]
        except (TypeError, ValueError):
            return []

    @classmethod
    def _cosine_similarity(cls, left: Iterable[float] | None, right: Iterable[float] | None) -> float:
        left_vector = cls._safe_vector(left)
        right_vector = cls._safe_vector(right)
        if not left_vector or not right_vector or len(left_vector) != len(right_vector):
            return 0.0
        dot = sum(a * b for a, b in zip(left_vector, right_vector))
        left_norm = sum(value * value for value in left_vector) ** 0.5
        right_norm = sum(value * value for value in right_vector) ** 0.5
        if left_norm <= 0.0 or right_norm <= 0.0:
            return 0.0
        return dot / (left_norm * right_norm)

    def search_similar_examples(
        self,
        db: Session,
        question: str,
        *,
        table_name: str | None = None,
    ) -> str:
        question_text = str(question or "").strip()
        if not question_text:
            return "（暂无历史参考）"

        query = (
            db.query(Text2SQLQueryLog)
            .filter(Text2SQLQueryLog.status == "success")
            .filter(Text2SQLQueryLog.final_sql.isnot(None))
            .order_by(Text2SQLQueryLog.created_at.desc())
            .limit(self._candidate_limit)
        )
        logs = list(query.all())
        if not logs:
            return "（暂无历史参考）"

        table_key = self._normalize_identifier(table_name)
        if table_key:
            logs = [
                log
                for log in logs
                if table_key in self._parse_selected_tables(getattr(log, "selected_tables", None))
            ]
        if not logs:
            return "（暂无历史参考）"

        try:
            embedder = get_embeddings()
            question_vector = embedder.embed_query(question_text)
            scored_logs: list[tuple[float, Text2SQLQueryLog]] = []
            for log in logs:
                log_question = str(getattr(log, "question", "") or "").strip()
                if not log_question:
                    continue
                similarity = self._cosine_similarity(question_vector, embedder.embed_query(log_question))
                if similarity <= 0.0:
                    continue
                scored_logs.append((float(similarity), log))
        except Exception:  # noqa: BLE001
            # 兜底：embedding 异常时按最近成功日志返回。
            scored_logs = [(1.0, log) for log in logs]

        if not scored_logs:
            return "（暂无历史参考）"

        scored_logs.sort(
            key=lambda item: (
                -float(item[0]),
                -int(getattr(item[1], "id", 0)),
            )
        )
        examples = scored_logs[: self._max_examples]

        lines: list[str] = []
        for index, (_, log) in enumerate(examples, 1):
            sql_text = str(getattr(log, "final_sql", "") or "").strip()
            if not sql_text:
                continue
            lines.append(f"示例{index}：")
            lines.append(f"  问题：{str(getattr(log, 'question', '') or '').strip()}")
            lines.append(f"  SQL：{sql_text}")
        return "\n".join(lines) if lines else "（暂无历史参考）"
