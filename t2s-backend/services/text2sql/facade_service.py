from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from core.config import settings
from services.text2sql.config_service import Text2SQLConfigService
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.executor_service import Text2SQLExecutorService
from services.text2sql.field_inference_service import Text2SQLFieldInferenceService
from services.text2sql.generator_service import Text2SQLGeneratorService
from services.text2sql.log_service import Text2SQLLogService
from services.text2sql.repair_service import Text2SQLRepairService
from services.text2sql.schema_service import Text2SQLSchemaService
from services.text2sql.summary_service import Text2SQLSummaryService
from services.text2sql.validator_service import Text2SQLValidatorService

_QUESTION_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")
GLOBAL_QUERY_USER_ID = 1

_console_logger = logging.getLogger("text2sql.console")
if not _console_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    _console_logger.addHandler(_handler)
_console_logger.setLevel(logging.INFO)
_console_logger.propagate = False


@dataclass
class SQLAttemptResult:
    generated_sql: str
    final_sql: str
    is_valid: bool
    validation_message: str
    repair_attempts: int


class Text2SQLFacadeService:
    def __init__(
        self,
        *,
        connection_service: Text2SQLConnectionService,
        schema_service: Text2SQLSchemaService,
        config_service: Text2SQLConfigService,
        log_service: Text2SQLLogService,
    ) -> None:
        self.connection_service = connection_service
        self.schema_service = schema_service
        self.config_service = config_service
        self.log_service = log_service

        self.validator_service = Text2SQLValidatorService()
        self.generator_service = Text2SQLGeneratorService(self._get_model, schema_service)
        self.repair_service = Text2SQLRepairService(self._get_model, schema_service, self._ensure_limit)
        self.executor_service = Text2SQLExecutorService(self.connection_service.get_engine, self._ensure_limit)
        self.summary_service = Text2SQLSummaryService(self._get_model)
        self.field_inference_service = Text2SQLFieldInferenceService(self._get_model)

        self._model: ChatOpenAI | None = None
        self._model_key = ""

    def query(self, question: str, db: Session, runtime_config: dict | None = None) -> dict:
        runtime = dict(runtime_config or {})
        selected_tables = self._normalize_table_list(runtime.get("selected_tables"))
        prompt_hint = str(runtime.get("prompt_hint") or "")
        request_id = str(runtime.get("request_id") or uuid.uuid4().hex[:8])

        start = time.monotonic_ns()
        generated_sql: str | None = None
        final_sql: str | None = None
        repaired = False

        _console_logger.info(
            "[query:%s] start question=%s",
            request_id,
            self._truncate_text(question, 400),
        )

        try:
            payload = self._run_pipeline(
                db=db,
                question=question,
                selected_tables=selected_tables,
                prompt_hint=prompt_hint,
                execute_sql=True,
            )
            generated_sql = payload["generated_sql"]
            final_sql = payload["sql"]
            repaired = bool(payload.get("repaired"))
            effective_tables = self._normalize_table_list(payload.get("selected_tables") or selected_tables)

            duration_ms = int((time.monotonic_ns() - start) / 1_000_000)
            if settings.TEXT2SQL_QUERY_LOG_ENABLED:
                self.log_service.create_success_log(
                    db=db,
                    user_id=GLOBAL_QUERY_USER_ID,
                    question=question,
                    generated_sql=generated_sql,
                    final_sql=final_sql,
                    runtime_config={"selected_tables": effective_tables, "prompt_hint": prompt_hint},
                    row_count=len(payload["rows"]),
                    duration_ms=duration_ms,
                    repaired=repaired,
                )

            _console_logger.info(
                "[query:%s] success tables=%s duration_ms=%s row_count=%s sql=%s sample_rows=%s",
                request_id,
                json.dumps(effective_tables, ensure_ascii=False),
                duration_ms,
                len(payload.get("rows") or []),
                self._truncate_text(final_sql, 600),
                json.dumps(self._sample_rows_for_log(payload.get("rows") or []), ensure_ascii=False),
            )
            return payload
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic_ns() - start) / 1_000_000)
            if settings.TEXT2SQL_QUERY_LOG_ENABLED:
                self.log_service.create_failed_log(
                    db=db,
                    user_id=GLOBAL_QUERY_USER_ID,
                    question=question,
                    generated_sql=generated_sql,
                    final_sql=final_sql,
                    runtime_config={"selected_tables": selected_tables, "prompt_hint": prompt_hint},
                    error_message=str(exc),
                    duration_ms=duration_ms,
                    repaired=repaired,
                )
            _console_logger.exception(
                "[query:%s] failed duration_ms=%s error=%s",
                request_id,
                duration_ms,
                self._truncate_text(str(exc), 400),
            )
            raise

    def debug_generate(self, question: str, db: Session, runtime_config: dict | None = None) -> dict:
        runtime = dict(runtime_config or {})
        selected_tables = self._normalize_table_list(runtime.get("selected_tables"))
        prompt_hint = str(runtime.get("prompt_hint") or "")
        request_id = str(runtime.get("request_id") or uuid.uuid4().hex[:8])

        _console_logger.info(
            "[debug:%s] start question=%s",
            request_id,
            self._truncate_text(question, 400),
        )
        try:
            result = self._run_pipeline(
                db=db,
                question=question,
                selected_tables=selected_tables,
                prompt_hint=prompt_hint,
                execute_sql=False,
            )
            _console_logger.info(
                "[debug:%s] done validation=%s sql=%s",
                request_id,
                bool(result.get("validation_passed")),
                self._truncate_text(str(result.get("sql") or ""), 600),
            )
            return result
        except Exception as exc:  # noqa: BLE001
            _console_logger.exception(
                "[debug:%s] failed error=%s",
                request_id,
                self._truncate_text(str(exc), 400),
            )
            raise

    def list_schema_overview(self, db: Session, table_names: list[str] | None = None):
        return self.schema_service.list_schema_overview(db, table_names)

    def _run_pipeline(
        self,
        *,
        db: Session,
        question: str,
        selected_tables: list[str],
        prompt_hint: str,
        execute_sql: bool,
    ) -> dict:
        route = self._route_tables(db, question, selected_tables)
        candidates = route["candidates"]
        if not candidates:
            raise ValueError(
                str(route.get("clarify_question") or "\u5f53\u524d\u95ee\u9898\u672a\u5339\u914d\u5230\u53ef\u67e5\u8be2\u7684\u6570\u636e\u8868")
            )

        repair_rounds = max(0, int(settings.TEXT2SQL_AUTO_REPAIR_ROUNDS))
        result = self._evaluate_candidates(
            db=db,
            question=question,
            candidate_tables=candidates,
            prompt_hint=prompt_hint,
            repair_rounds=repair_rounds,
        )
        if not result.is_valid:
            raise ValueError(f"SQL \u6821\u9a8c\u5931\u8d25: {result.validation_message}")

        payload = {
            "mode": route["mode"],
            "candidate_tables": candidates,
            "route_scores": route["scores"],
            "selected_tables": candidates,
            "generated_sql": result.generated_sql,
            "sql": result.final_sql,
            "validation_passed": result.is_valid,
            "validation_message": result.validation_message,
            "repair_attempts": result.repair_attempts,
            "repaired": result.repair_attempts > 0,
        }

        if execute_sql:
            columns, rows = self.executor_service.execute_sql(db, result.final_sql)
            payload.update(
                {
                    "columns": columns,
                    "rows": rows,
                    "answer": self.summary_service.summarize_result(question, result.final_sql, columns, rows),
                    "field_inference": self.field_inference_service.infer_fields(
                        question=question,
                        sql=result.final_sql,
                        columns=columns,
                        rows=rows,
                    ),
                }
            )

        return payload

    def _evaluate_candidates(
        self,
        *,
        db: Session,
        question: str,
        candidate_tables: list[str],
        prompt_hint: str,
        repair_rounds: int,
    ) -> SQLAttemptResult:
        runtime_config = {
            "selected_tables": candidate_tables,
            "prompt_hint": prompt_hint,
        }

        generated_sql = self.generator_service.generate_sql(
            db=db,
            question=question,
            runtime_config=runtime_config,
        )
        final_sql = self._ensure_limit(generated_sql)
        table_columns_map = self.schema_service.get_live_table_columns_map(db, candidate_tables)
        is_valid, message = self.validator_service.validate_sql(
            final_sql,
            allowed_tables=candidate_tables,
            table_columns_map=table_columns_map,
            max_tables=settings.TEXT2SQL_MAX_JOIN_TABLES,
        )

        repair_attempts = 0
        while not is_valid and repair_attempts < repair_rounds:
            repair_attempts += 1
            repaired_sql = self.repair_service.repair_sql(
                db=db,
                question=question,
                failed_sql=final_sql,
                error_message=message,
                runtime_config=runtime_config,
            )
            final_sql = self._ensure_limit(repaired_sql)
            is_valid, message = self.validator_service.validate_sql(
                final_sql,
                allowed_tables=candidate_tables,
                table_columns_map=table_columns_map,
                max_tables=settings.TEXT2SQL_MAX_JOIN_TABLES,
            )

        return SQLAttemptResult(
            generated_sql=generated_sql,
            final_sql=final_sql,
            is_valid=is_valid,
            validation_message=message,
            repair_attempts=repair_attempts,
        )

    def _route_tables(self, db: Session, question: str, selected_tables: list[str]) -> dict:
        table_columns_map = self.schema_service.get_live_table_columns_map(db, selected_tables or None)
        if not table_columns_map:
            return {
                "mode": "miss",
                "candidates": [],
                "scores": {},
                "clarify_question": "\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6ca1\u6709\u53ef\u67e5\u8be2\u7684\u6570\u636e\u8868",
            }

        scores = self._score_table_candidates(question, table_columns_map)
        ranked = sorted(table_columns_map.keys(), key=lambda t: (-scores.get(t, 0.0), t))
        max_candidates = max(1, int(settings.TABLE_ROUTE_MAX_CANDIDATES))
        max_score = max(scores.values()) if scores else 0.0

        if len(ranked) == 1:
            return {"mode": "single", "candidates": ranked, "scores": scores, "clarify_question": ""}

        if max_score <= 0:
            no_signal_cap = min(len(ranked), max(max_candidates, 20))
            return {
                "mode": "no_signal",
                "candidates": ranked[:no_signal_cap],
                "scores": scores,
                "clarify_question": "\u8def\u7531\u4fe1\u53f7\u8f83\u5f31\uff0c\u5df2\u6269\u5927\u5019\u9009\u8868\u8303\u56f4",
            }

        top = ranked[:max_candidates]
        if len(top) == 1:
            return {"mode": "single", "candidates": top, "scores": scores, "clarify_question": ""}

        delta = float(settings.TABLE_ROUTE_AMBIGUITY_DELTA)
        if (scores.get(top[0], 0.0) - scores.get(top[1], 0.0)) > delta:
            return {
                "mode": "single",
                "candidates": [top[0]],
                "scores": scores,
                "clarify_question": "",
            }

        return {
            "mode": "ambiguous",
            "candidates": top,
            "scores": scores,
            "clarify_question": "\u5019\u9009\u8868\u5b58\u5728\u6b67\u4e49\uff0c\u8bf7\u8865\u5145\u66f4\u5177\u4f53\u7684\u7b5b\u9009\u6761\u4ef6",
        }

    @staticmethod
    def _score_table_candidates(question: str, table_columns_map: dict[str, set[str]]) -> dict[str, float]:
        question_text = str(question or "").lower()
        question_tokens = {token.lower() for token in _QUESTION_TOKEN_PATTERN.findall(question_text) if token}
        scores: dict[str, float] = {}

        for table_name, columns in table_columns_map.items():
            norm_table = table_name.strip().lower()
            score = 0.0
            if norm_table and norm_table in question_text:
                score += 2.0

            table_tokens = {
                token.lower()
                for token in re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", norm_table)
                if token
            }
            for token in table_tokens:
                if token in question_tokens:
                    score += 1.0

            for column in columns:
                norm_col = str(column).strip().lower()
                if norm_col and norm_col in question_text:
                    score += 0.2

            scores[table_name] = round(score, 6)
        return scores

    @staticmethod
    def _normalize_table_list(tables) -> list[str]:
        if not tables:
            return []

        if isinstance(tables, str):
            raw_tables = [tables]
        elif isinstance(tables, (list, tuple, set)):
            raw_tables = list(tables)
        else:
            raw_tables = [tables]

        result: list[str] = []
        seen = set()
        for item in raw_tables:
            table = str(item).strip()
            if not table:
                continue
            key = table.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(table)
        return result

    @staticmethod
    def _ensure_limit(sql: str) -> str:
        sql_text = str(sql or "").strip().rstrip(";")
        if not sql_text:
            return f"SELECT 1 LIMIT {int(settings.TEXT2SQL_MAX_ROWS)};"
        if re.search(r"\blimit\b", sql_text, flags=re.IGNORECASE):
            return sql_text + ";"
        return f"{sql_text} LIMIT {int(settings.TEXT2SQL_MAX_ROWS)};"

    @staticmethod
    def _truncate_text(value: str | None, max_len: int) -> str:
        text = str(value or "")
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    @classmethod
    def _sample_rows_for_log(cls, rows: list[dict], max_rows: int = 3) -> list[dict]:
        sampled: list[dict] = []
        for row in rows[:max_rows]:
            sampled.append({str(k): cls._truncate_text(str(v), 80) for k, v in row.items()})
        return sampled

    def _get_model(self) -> ChatOpenAI | None:
        if not (
            settings.EFFECTIVE_LLM_BASE_URL
            and settings.EFFECTIVE_LLM_API_KEY
            and settings.EFFECTIVE_LLM_MODEL
        ):
            return None

        current_key = "|".join(
            [
                settings.EFFECTIVE_LLM_BASE_URL,
                settings.EFFECTIVE_LLM_MODEL,
                settings.EFFECTIVE_LLM_API_KEY,
            ]
        )
        if self._model is None or self._model_key != current_key:
            self._model = ChatOpenAI(
                base_url=settings.EFFECTIVE_LLM_BASE_URL.rstrip("/"),
                api_key=settings.EFFECTIVE_LLM_API_KEY,
                model=settings.EFFECTIVE_LLM_MODEL,
                temperature=0.0,
                request_timeout=settings.LLM_TIMEOUT,
            )
            self._model_key = current_key

        return self._model
