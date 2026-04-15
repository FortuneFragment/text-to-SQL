from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from sqlglot import exp, parse_one
from sqlalchemy.orm import Session

from core.config import settings
from services.text2sql.config_service import Text2SQLConfigService
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.executor_service import Text2SQLExecutorService
from services.text2sql.field_permission_service import Text2SQLFieldPermissionService
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
    """封装SQLAttemptResult相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    generated_sql: str
    final_sql: str
    is_valid: bool
    validation_message: str
    repair_attempts: int


class Text2SQLFacadeService:
    """封装流程编排。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(
        self,
        *,
        connection_service: Text2SQLConnectionService,
        schema_service: Text2SQLSchemaService,
        config_service: Text2SQLConfigService,
        field_permission_service: Text2SQLFieldPermissionService,
        log_service: Text2SQLLogService,
    ) -> None:
        """处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self.connection_service`。
        self.connection_service = connection_service
        self.schema_service = schema_service
        self.config_service = config_service
        self.field_permission_service = field_permission_service
        self.log_service = log_service

        # 2. 变量构建：计算并更新 `self.validator_service`。
        self.validator_service = Text2SQLValidatorService()
        self.generator_service = Text2SQLGeneratorService(self._get_model, schema_service)
        self.repair_service = Text2SQLRepairService(self._get_model, schema_service, self._ensure_limit)
        self.executor_service = Text2SQLExecutorService(self.connection_service.get_engine, self._ensure_limit)
        self.summary_service = Text2SQLSummaryService(self._get_model)
        self.field_inference_service = Text2SQLFieldInferenceService(self._get_model)

        # 3. 变量构建：计算并更新 `self._model: ChatOpenAI | None`。
        self._model: ChatOpenAI | None = None
        self._model_key = ""

    def query(self, question: str, db: Session, runtime_config: dict | None = None) -> dict:
        """查询相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `runtime`。
        runtime = dict(runtime_config or {})
        selected_tables = self._normalize_table_list(runtime.get("selected_tables"))
        prompt_hint = str(runtime.get("prompt_hint") or "")
        queryable_columns_map = self.field_permission_service.get_queryable_columns_map(
            db,
            selected_tables,
        )
        request_id = str(runtime.get("request_id") or uuid.uuid4().hex[:8])

        # 2. 变量构建：计算并更新 `start`。
        start = time.monotonic_ns()
        generated_sql: str | None = None
        final_sql: str | None = None
        repaired = False

        # 3. 核心处理：执行当前阶段的业务逻辑。
        _console_logger.info(
            "[query:%s] start question=%s",
            request_id,
            self._truncate_text(question, 400),
        )

        # 4. 核心处理：执行当前阶段的业务逻辑。
        try:
            payload = self._run_pipeline(
                db=db,
                question=question,
                selected_tables=selected_tables,
                prompt_hint=prompt_hint,
                queryable_columns_map=queryable_columns_map,
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
        """中文备注：调试generate相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `runtime`。
        runtime = dict(runtime_config or {})
        selected_tables = self._normalize_table_list(runtime.get("selected_tables"))
        prompt_hint = str(runtime.get("prompt_hint") or "")
        queryable_columns_map = self.field_permission_service.get_queryable_columns_map(
            db,
            selected_tables,
        )
        request_id = str(runtime.get("request_id") or uuid.uuid4().hex[:8])

        # 2. 核心处理：执行当前阶段的业务逻辑。
        _console_logger.info(
            "[debug:%s] start question=%s",
            request_id,
            self._truncate_text(question, 400),
        )
        # 3. 核心处理：执行当前阶段的业务逻辑。
        try:
            result = self._run_pipeline(
                db=db,
                question=question,
                selected_tables=selected_tables,
                prompt_hint=prompt_hint,
                queryable_columns_map=queryable_columns_map,
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
        """中文备注：列出schema overview相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return self.schema_service.list_schema_overview(db, table_names)

    def _run_pipeline(
        self,
        *,
        db: Session,
        question: str,
        selected_tables: list[str],
        prompt_hint: str,
        queryable_columns_map: dict[str, set[str]],
        execute_sql: bool,
    ) -> dict:
        """中文备注：处理pipeline相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `route`。
        route = self._route_tables(
            db,
            question,
            selected_tables,
            queryable_columns_map=queryable_columns_map,
        )
        candidates = route["candidates"]
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not candidates:
            raise ValueError(
                str(route.get("clarify_question") or "\u5f53\u524d\u95ee\u9898\u672a\u5339\u914d\u5230\u53ef\u67e5\u8be2\u7684\u6570\u636e\u8868")
            )

        # 3. 变量构建：计算并更新 `repair_rounds`。
        repair_rounds = max(0, int(settings.TEXT2SQL_AUTO_REPAIR_ROUNDS))
        result = self._evaluate_candidates(
            db=db,
            question=question,
            candidate_tables=candidates,
            prompt_hint=prompt_hint,
            queryable_columns_map=queryable_columns_map,
            repair_rounds=repair_rounds,
        )
        # 4. 条件分支：根据当前状态选择不同处理路径。
        if not result.is_valid:
            raise ValueError(f"SQL \u6821\u9a8c\u5931\u8d25: {result.validation_message}")

        # 5. 结果组装：将当前阶段产物写入结构化结果。
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

        # 6. 条件分支：根据当前状态选择不同处理路径。
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

        # 7. 返回结果：输出当前函数最终结果。
        return payload

    def _evaluate_candidates(
        self,
        *,
        db: Session,
        question: str,
        candidate_tables: list[str],
        prompt_hint: str,
        queryable_columns_map: dict[str, set[str]],
        repair_rounds: int,
    ) -> SQLAttemptResult:
        """中文备注：处理candidates相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `candidate_columns_map`。
        candidate_columns_map = {
            table_name: set(queryable_columns_map.get(table_name, set()))
            for table_name in candidate_tables
        }
        table_columns_map = self.schema_service.get_live_table_columns_map(
            db,
            candidate_tables,
            queryable_columns_map=candidate_columns_map,
        )
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not table_columns_map:
            raise ValueError("可查询字段为空，请先在字段页开启至少一个字段")

        # 3. 变量构建：计算并更新 `runtime_config`。
        runtime_config = {
            "selected_tables": candidate_tables,
            "prompt_hint": prompt_hint,
            "queryable_columns_map": candidate_columns_map,
        }

        # 4. 变量构建：计算并更新 `generated_sql`。
        generated_sql = self.generator_service.generate_sql(
            db=db,
            question=question,
            runtime_config=runtime_config,
        )
        generated_sql = self._expand_select_star(generated_sql, table_columns_map)
        final_sql = self._ensure_limit(generated_sql)
        is_valid, message = self.validator_service.validate_sql(
            final_sql,
            allowed_tables=candidate_tables,
            table_columns_map=table_columns_map,
            max_tables=settings.TEXT2SQL_MAX_JOIN_TABLES,
        )

        # 5. 变量构建：计算并更新 `repair_attempts`。
        repair_attempts = 0
        # 6. 核心处理：执行当前阶段的业务逻辑。
        while not is_valid and repair_attempts < repair_rounds:
            repair_attempts += 1
            repaired_sql = self.repair_service.repair_sql(
                db=db,
                question=question,
                failed_sql=final_sql,
                error_message=message,
                runtime_config=runtime_config,
            )
            repaired_sql = self._expand_select_star(repaired_sql, table_columns_map)
            final_sql = self._ensure_limit(repaired_sql)
            is_valid, message = self.validator_service.validate_sql(
                final_sql,
                allowed_tables=candidate_tables,
                table_columns_map=table_columns_map,
                max_tables=settings.TEXT2SQL_MAX_JOIN_TABLES,
            )

        # 7. 返回结果：输出当前函数最终结果。
        return SQLAttemptResult(
            generated_sql=generated_sql,
            final_sql=final_sql,
            is_valid=is_valid,
            validation_message=message,
            repair_attempts=repair_attempts,
        )

    def _route_tables(
        self,
        db: Session,
        question: str,
        selected_tables: list[str],
        queryable_columns_map: dict[str, set[str]],
    ) -> dict:
        """中文备注：路由tables相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `table_columns_map`。
        table_columns_map = self.schema_service.get_live_table_columns_map(
            db,
            selected_tables,
            queryable_columns_map=queryable_columns_map,
        )
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not table_columns_map:
            return {
                "mode": "miss",
                "candidates": [],
                "scores": {},
                "clarify_question": "\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6ca1\u6709\u53ef\u67e5\u8be2\u7684\u6570\u636e\u8868",
            }

        # 3. 变量构建：计算并更新 `scores`。
        scores = self._score_table_candidates(question, table_columns_map)
        ranked = sorted(table_columns_map.keys(), key=lambda t: (-scores.get(t, 0.0), t))
        max_candidates = max(1, int(settings.TABLE_ROUTE_MAX_CANDIDATES))
        max_score = max(scores.values()) if scores else 0.0

        # 4. 条件分支：根据当前状态选择不同处理路径。
        if len(ranked) == 1:
            return {"mode": "single", "candidates": ranked, "scores": scores, "clarify_question": ""}

        # 5. 条件分支：根据当前状态选择不同处理路径。
        if max_score <= 0:
            no_signal_cap = min(len(ranked), max(max_candidates, 20))
            return {
                "mode": "no_signal",
                "candidates": ranked[:no_signal_cap],
                "scores": scores,
                "clarify_question": "\u8def\u7531\u4fe1\u53f7\u8f83\u5f31\uff0c\u5df2\u6269\u5927\u5019\u9009\u8868\u8303\u56f4",
            }

        # 6. 变量构建：计算并更新 `top`。
        top = ranked[:max_candidates]
        # 7. 条件分支：根据当前状态选择不同处理路径。
        if len(top) == 1:
            return {"mode": "single", "candidates": top, "scores": scores, "clarify_question": ""}

        # 8. 变量构建：计算并更新 `delta`。
        delta = float(settings.TABLE_ROUTE_AMBIGUITY_DELTA)
        # 9. 条件分支：根据当前状态选择不同处理路径。
        if (scores.get(top[0], 0.0) - scores.get(top[1], 0.0)) > delta:
            return {
                "mode": "single",
                "candidates": [top[0]],
                "scores": scores,
                "clarify_question": "",
            }

        # 10. 返回结果：输出当前函数最终结果。
        return {
            "mode": "ambiguous",
            "candidates": top,
            "scores": scores,
            "clarify_question": "\u5019\u9009\u8868\u5b58\u5728\u6b67\u4e49\uff0c\u8bf7\u8865\u5145\u66f4\u5177\u4f53\u7684\u7b5b\u9009\u6761\u4ef6",
        }

    @staticmethod
    def _score_table_candidates(question: str, table_columns_map: dict[str, set[str]]) -> dict[str, float]:
        """中文备注：评分table candidates相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `question_text`。
        question_text = str(question or "").lower()
        question_tokens = {token.lower() for token in _QUESTION_TOKEN_PATTERN.findall(question_text) if token}
        scores: dict[str, float] = {}

        # 2. 迭代处理：遍历集合并逐项构建结果。
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
        # 3. 返回结果：输出当前函数最终结果。
        return scores

    @staticmethod
    def _normalize_table_list(tables) -> list[str]:
        """规范化table list相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if not tables:
            return []

        # 2. 条件分支：根据当前状态选择不同处理路径。
        if isinstance(tables, str):
            raw_tables = [tables]
        elif isinstance(tables, (list, tuple, set)):
            raw_tables = list(tables)
        else:
            raw_tables = [tables]

        # 3. 变量构建：计算并更新 `result: list[str]`。
        result: list[str] = []
        seen = set()
        # 4. 迭代处理：遍历集合并逐项构建结果。
        for item in raw_tables:
            table = str(item).strip()
            if not table:
                continue
            key = table.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(table)
        # 5. 返回结果：输出当前函数最终结果。
        return result

    @staticmethod
    def _expand_select_star(sql: str, table_columns_map: dict[str, set[str]]) -> str:
        """中文备注：处理select star相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `sql_text`。
        sql_text = str(sql or "").strip().rstrip(";")
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not sql_text:
            return "SELECT 1;"

        # 3. 核心处理：执行当前阶段的业务逻辑。
        try:
            tree = parse_one(sql_text, read="mysql")
        except Exception:  # noqa: BLE001
            return sql_text + ";"

        # 4. 条件分支：根据当前状态选择不同处理路径。
        if not isinstance(tree, exp.Select):
            return sql_text + ";"

        # 5. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        normalized_table_columns_map: dict[str, list[str]] = {}
        # 6. 迭代处理：遍历集合并逐项构建结果。
        for table_name, columns in (table_columns_map or {}).items():
            normalized_table = Text2SQLValidatorService.normalize_table_identifier(table_name)
            if not normalized_table:
                continue
            normalized_table_columns_map[normalized_table] = sorted(
                [str(column) for column in (columns or set()) if str(column).strip()]
            )

        # 7. 变量构建：计算并更新 `alias_map`。
        alias_map = Text2SQLValidatorService.build_alias_map(tree)
        normalized_alias_map = {
            Text2SQLValidatorService.normalize_identifier(alias): str(real_table)
            for alias, real_table in alias_map.items()
            if alias and real_table
        }

        # 8. 变量构建：计算并更新 `table_order: list[tuple[str, str]]`。
        table_order: list[tuple[str, str]] = []
        seen_tables: set[str] = set()
        # 9. 迭代处理：遍历集合并逐项构建结果。
        for table in tree.find_all(exp.Table):
            if not table.name:
                continue
            normalized_table = Text2SQLValidatorService.normalize_table_identifier(str(table.name))
            if not normalized_table or normalized_table in seen_tables:
                continue
            seen_tables.add(normalized_table)
            qualifier = str(table.alias_or_name or table.name)
            table_order.append((normalized_table, qualifier))

        # 10. 变量构建：计算并更新 `replaced`。
        replaced = False
        expanded_expressions: list[exp.Expression] = []
        # 11. 迭代处理：遍历集合并逐项构建结果。
        for expression in list(tree.expressions):
            if isinstance(expression, exp.Star):
                replaced = True
                for table_name, qualifier in table_order:
                    for column_name in normalized_table_columns_map.get(table_name, []):
                        if len(table_order) > 1:
                            expanded_expressions.append(exp.column(column_name, table=qualifier))
                        else:
                            expanded_expressions.append(exp.column(column_name))
                continue

            if isinstance(expression, exp.Column) and isinstance(expression.this, exp.Star):
                table_alias = str(expression.table or "")
                alias_key = Text2SQLValidatorService.normalize_identifier(table_alias)
                resolved_table = normalized_alias_map.get(alias_key, table_alias)
                normalized_table = Text2SQLValidatorService.normalize_table_identifier(resolved_table)
                selected_columns = normalized_table_columns_map.get(normalized_table, [])
                if selected_columns:
                    replaced = True
                    qualifier = table_alias or resolved_table
                    for column_name in selected_columns:
                        expanded_expressions.append(exp.column(column_name, table=qualifier))
                    continue

            expanded_expressions.append(expression)

        # 12. 条件分支：根据当前状态选择不同处理路径。
        if replaced and expanded_expressions:
            tree.set("expressions", expanded_expressions)

        # 13. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        normalized_sql = tree.sql(dialect="mysql").strip().rstrip(";")
        # 14. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        return normalized_sql + ";"

    @staticmethod
    def _is_statistical_query(sql_text: str, tree: exp.Expression | None) -> bool:
        """中文备注：处理statistical query相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if tree is not None:
            if tree.args.get("group") is not None or tree.args.get("having") is not None:
                return True
            if any(tree.find(func_type) is not None for func_type in (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
                return True

        # 2. 返回结果：输出当前函数最终结果。
        return bool(
            re.search(
                r"\b(count|sum|avg|min|max)\s*\(|\bgroup\s+by\b|\bhaving\b",
                sql_text,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _strip_top_level_limit(sql_text: str, tree: exp.Expression | None) -> str:
        """中文备注：清理top level limit相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if tree is not None and tree.args.get("limit") is not None:
            copied = tree.copy()
            copied.set("limit", None)
            return copied.sql(dialect="mysql").strip().rstrip(";")

        # 2. 返回结果：输出当前函数最终结果。
        return re.sub(
            r"\s+limit\s+\d+\s*(,\s*\d+)?\s*$",
            "",
            sql_text,
            flags=re.IGNORECASE,
        ).strip()

    @classmethod
    def _ensure_limit(cls, sql: str) -> str:
        """中文备注：确保limit相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `sql_text`。
        sql_text = str(sql or "").strip().rstrip(";")
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not sql_text:
            return f"SELECT 1 LIMIT {int(settings.TEXT2SQL_MAX_ROWS)};"

        # 3. 核心处理：执行当前阶段的业务逻辑。
        tree: exp.Expression | None
        # 4. 核心处理：执行当前阶段的业务逻辑。
        try:
            tree = parse_one(sql_text, read="mysql")
        except Exception:  # noqa: BLE001
            tree = None

        # 5. 条件分支：根据当前状态选择不同处理路径。
        if cls._is_statistical_query(sql_text, tree):
            sql_without_limit = cls._strip_top_level_limit(sql_text, tree)
            return (sql_without_limit or sql_text).rstrip(";") + ";"

        # 6. 条件分支：根据当前状态选择不同处理路径。
        if tree is not None and tree.args.get("limit") is not None:
            return tree.sql(dialect="mysql").strip().rstrip(";") + ";"

        # 7. 条件分支：根据当前状态选择不同处理路径。
        if re.search(r"\blimit\b", sql_text, flags=re.IGNORECASE):
            return sql_text + ";"

        # 8. 返回结果：输出当前函数最终结果。
        return f"{sql_text} LIMIT {int(settings.TEXT2SQL_MAX_ROWS)};"

    @staticmethod
    def _truncate_text(value: str | None, max_len: int) -> str:
        """中文备注：截断text相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `text`。
        text = str(value or "")
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if len(text) <= max_len:
            return text
        # 3. 返回结果：输出当前函数最终结果。
        return text[: max_len - 3] + "..."

    @classmethod
    def _sample_rows_for_log(cls, rows: list[dict], max_rows: int = 3) -> list[dict]:
        """中文备注：采样rows for log相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `sampled: list[dict]`。
        sampled: list[dict] = []
        # 2. 迭代处理：遍历集合并逐项构建结果。
        for row in rows[:max_rows]:
            sampled.append({str(k): cls._truncate_text(str(v), 80) for k, v in row.items()})
        # 3. 返回结果：输出当前函数最终结果。
        return sampled

    def _get_model(self) -> ChatOpenAI | None:
        """中文备注：获取model相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if not (
            settings.EFFECTIVE_LLM_BASE_URL
            and settings.EFFECTIVE_LLM_API_KEY
            and settings.EFFECTIVE_LLM_MODEL
        ):
            return None

        # 2. 变量构建：计算并更新 `current_key`。
        current_key = "|".join(
            [
                settings.EFFECTIVE_LLM_BASE_URL,
                settings.EFFECTIVE_LLM_MODEL,
                settings.EFFECTIVE_LLM_API_KEY,
            ]
        )
        # 3. 条件分支：根据当前状态选择不同处理路径。
        if self._model is None or self._model_key != current_key:
            self._model = ChatOpenAI(
                base_url=settings.EFFECTIVE_LLM_BASE_URL.rstrip("/"),
                api_key=settings.EFFECTIVE_LLM_API_KEY,
                model=settings.EFFECTIVE_LLM_MODEL,
                temperature=0.0,
                request_timeout=settings.LLM_TIMEOUT,
            )
            self._model_key = current_key

        # 4. 返回结果：输出当前函数最终结果。
        return self._model
