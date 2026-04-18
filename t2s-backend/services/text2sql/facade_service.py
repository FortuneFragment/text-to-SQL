from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlglot import exp, parse_one
from sqlalchemy.orm import Session

from core.config import settings
from services.text2sql.config_service import Text2SQLConfigService
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.enum_hint_service import Text2SQLEnumHintService
from services.text2sql.executor_service import Text2SQLExecutorService
from services.text2sql.few_shot_service import Text2SQLFewShotService
from services.text2sql.field_permission_service import Text2SQLFieldPermissionService
from services.text2sql.generator_service import Text2SQLGeneratorService
from services.text2sql.log_service import Text2SQLLogService
from services.text2sql.repair_service import Text2SQLRepairService
from services.text2sql.schema_service import Text2SQLSchemaService
from services.text2sql.summary_service import Text2SQLSummaryService
from services.text2sql.vector_service import Text2SQLVectorService
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

_TABLE_SELECTION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "你是数据表选择器。根据用户的问题，从下面的候选表中选出最相关的一张表。\n"
            "判断依据：优先看表注释是否与问题的业务场景匹配，其次看字段名是否包含问题需要的数据。\n"
            "只输出表名本身，不要带引号、不要解释。\n\n"
            "候选表：\n{candidates_info}\n"
        ),
    ),
    ("human", "用户问题：{question}"),
])


@dataclass
class SQLAttemptResult:
    """描述一次 SQL 生成/修复后的校验结果。"""
    generated_sql: str
    final_sql: str
    is_valid: bool
    validation_message: str
    repair_attempts: int
    candidate_columns_map: dict[str, set[str]]

class Text2SQLFacadeService:
    """编排 Text2SQL 全链路：路由、生成、校验、修复、执行和总结。"""
    def __init__(
        self,
        *,
        connection_service: Text2SQLConnectionService,
        schema_service: Text2SQLSchemaService,
        config_service: Text2SQLConfigService,
        field_permission_service: Text2SQLFieldPermissionService,
        log_service: Text2SQLLogService,
    ) -> None:
        """组装各子服务并初始化模型缓存。"""
        self.connection_service = connection_service
        self.schema_service = schema_service
        self.config_service = config_service
        self.field_permission_service = field_permission_service
        self.log_service = log_service
        self.validator_service = Text2SQLValidatorService()
        self.generator_service = Text2SQLGeneratorService(self._get_model, schema_service)
        self.repair_service = Text2SQLRepairService(self._get_model, schema_service, self._ensure_limit)
        self.executor_service = Text2SQLExecutorService(self.connection_service.get_engine, self._ensure_limit)
        self.summary_service = Text2SQLSummaryService(self._get_model)
        self.vector_service = Text2SQLVectorService(kb_id=int(settings.TABLE_ROUTE_KB_ID or 0))
        self.few_shot_service = Text2SQLFewShotService(max_examples=3, candidate_limit=200)
        self.enum_hint_service = Text2SQLEnumHintService(self.connection_service.get_engine, self.schema_service)
        self._model: ChatOpenAI | None = None
        self._model_key = ""

    def query(self, question: str, db: Session, runtime_config: dict | None = None) -> dict:
        """执行完整问答流程并返回可直接展示的结果。"""
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
        """仅运行路由与 SQL 生成/校验，不执行数据库查询。"""
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
        """返回指定表范围内的 Schema 概览。"""
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
        """运行核心流水线，可按需执行 SQL 并补充总结信息。"""
        route = self._route_tables(
            db,
            question,
            selected_tables,
        )
        candidates = route["candidates"]
        if not candidates:
            raise ValueError(
                str(route.get("clarify_question") or "\u5f53\u524d\u95ee\u9898\u672a\u5339\u914d\u5230\u53ef\u67e5\u8be2\u7684\u6570\u636e\u8868")
            )

        candidate_columns_map = self.field_permission_service.get_queryable_columns_map(
            db,
            candidates,
        )
        enhanced_prompt_hint = prompt_hint
        if settings.TEXT2SQL_ENUM_HINT_ENABLED:
            enhanced_prompt_hint = self.enum_hint_service.build_prompt_hint(
                db=db,
                candidate_tables=candidates,
                queryable_columns_map=candidate_columns_map,
                base_prompt_hint=prompt_hint,
            )
        few_shot_examples = "（暂无历史参考）"
        try:
            few_shot_examples = self.few_shot_service.search_similar_examples(
                db,
                question,
                table_name=candidates[0] if candidates else None,
            )
        except Exception:  # noqa: BLE001
            _console_logger.exception("few-shot retrieval failed")
        repair_rounds = max(0, int(settings.TEXT2SQL_AUTO_REPAIR_ROUNDS))
        result = self._evaluate_candidates(
            db=db,
            question=question,
            candidate_tables=candidates,
            prompt_hint=enhanced_prompt_hint,
            few_shot_examples=few_shot_examples,
            candidate_columns_map=candidate_columns_map,
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
                    "field_inference": self.field_permission_service.build_query_field_comment_bindings(
                        db=db,
                        columns=columns,
                        table_names=candidates,
                        queryable_columns_map=result.candidate_columns_map,
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
        few_shot_examples: str,
        candidate_columns_map: dict[str, set[str]],
        repair_rounds: int,
    ) -> SQLAttemptResult:
        """针对候选表生成 SQL，并在失败时进行自动修复重试。"""
        table_columns_map = self.schema_service.get_live_table_columns_map(
            db,
            candidate_tables,
            queryable_columns_map=candidate_columns_map,
        )
        if not table_columns_map:
            raise ValueError("可查询字段为空，请先在字段页开启至少一个字段")
        runtime_config = {
            "selected_tables": candidate_tables,
            "prompt_hint": prompt_hint,
            "few_shot_examples": few_shot_examples,
            "queryable_columns_map": candidate_columns_map,
        }
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
            max_tables=1,
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
            repaired_sql = self._expand_select_star(repaired_sql, table_columns_map)
            final_sql = self._ensure_limit(repaired_sql)
            is_valid, message = self.validator_service.validate_sql(
                final_sql,
                allowed_tables=candidate_tables,
                table_columns_map=table_columns_map,
                max_tables=1,
            )
        return SQLAttemptResult(
            generated_sql=generated_sql,
            final_sql=final_sql,
            is_valid=is_valid,
            validation_message=message,
            repair_attempts=repair_attempts,
            candidate_columns_map=candidate_columns_map,
        )

    @staticmethod
    def _contains_chinese(value: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in value)

    @classmethod
    def _build_search_tokens(cls, text: str, *, max_tokens: int = 256) -> set[str]:
        token_set: set[str] = set()
        for raw in _QUESTION_TOKEN_PATTERN.findall(str(text or "").lower()):
            token = str(raw or "").strip().strip("_")
            if not token:
                continue

            if cls._contains_chinese(token):
                compact = token.replace("_", "")
                if compact:
                    token_set.add(compact)
                if len(compact) >= 2:
                    # 中文查询常是连续句子，补充 2-gram 提升“注释词/业务词”命中率。
                    max_grams = min(len(compact) - 1, 64)
                    for index in range(max_grams):
                        token_set.add(compact[index : index + 2])
            else:
                for part in re.split(r"[_\s]+", token):
                    normalized = part.strip()
                    if len(normalized) >= 2:
                        token_set.add(normalized)
                if len(token) >= 2:
                    token_set.add(token)

            if len(token_set) >= max_tokens:
                break
        return token_set

    @classmethod
    def _build_table_profiles(
        cls,
        table_options: list[dict[str, str]],
        table_columns_map: dict[str, set[str]] | None = None,
    ) -> dict[str, str]:
        """构建用于 token 打分的表 profile 文本。

        注意：字段名限制为最多 20 个，过多字段会导致 2-gram 打分时产生
        大量偶然命中，让不相关的大表得分虚高。字段名的主要作用是补充
        表名和注释无法覆盖的业务关键词。
        """
        profiles: dict[str, str] = {}
        for option in table_options:
            table_name = str(option.get("table_name") or "").strip()
            if not table_name:
                continue
            table_comment = str(option.get("table_comment") or "").strip()
            columns = sorted(
                [
                    str(column).strip()
                    for column in (table_columns_map or {}).get(table_name, set())
                    if str(column).strip()
                ]
            )
            # 只保留前 20 个字段名参与打分，避免大表 token 噪声
            if len(columns) > 20:
                columns = columns[:20]
            columns_text = " ".join(columns)
            profile_text = f"{table_name} {table_comment} {columns_text}".strip()
            profiles[table_name] = profile_text
        return profiles

    @classmethod
    def _score_table_profile_candidates(cls, question: str, table_profiles: dict[str, str]) -> dict[str, float]:
        question_tokens = cls._build_search_tokens(question, max_tokens=320)
        scores: dict[str, float] = {}
        for table_name, profile in table_profiles.items():
            profile_tokens = cls._build_search_tokens(profile, max_tokens=320)
            if not profile_tokens:
                scores[table_name] = 0.0
                continue

            overlap = len(profile_tokens.intersection(question_tokens))
            score = round(min(3.0, float(overlap) * 0.18), 6)
            scores[table_name] = score
        return scores

    def _route_tables(
        self,
        db: Session,
        question: str,
        selected_tables: list[str],
    ) -> dict:
        """路由候选表（仅保留单表模式，最终只返回一个候选表）。"""
        table_options = self.schema_service.list_table_options(db)
        option_profiles = self._build_table_profiles(table_options)
        option_comment_map = {
            str(option.get("table_name") or "").strip(): str(option.get("table_comment") or "").strip()
            for option in table_options
            if str(option.get("table_name") or "").strip()
        }
        option_lookup = {str(name).lower(): name for name in option_profiles.keys()}

        if selected_tables:
            route_scope, _ = self.schema_service.validate_selected_tables(db, selected_tables)
        else:
            route_scope = list(option_profiles.keys())
        route_scope = [name for name in route_scope if str(name).lower() in option_lookup]
        if not route_scope:
            return {
                "mode": "miss",
                "candidates": [],
                "scores": {},
                "clarify_question": "\u5f53\u524d\u672a\u914d\u7f6e\u53ef\u8def\u7531\u7684\u6570\u636e\u8868",
            }

        queryable_tables = self.field_permission_service.get_queryable_table_names(db, route_scope)
        if not queryable_tables:
            return {
                "mode": "miss",
                "candidates": [],
                "scores": {},
                "clarify_question": "\u5f53\u524d\u8868/\u5b57\u6bb5\u5f00\u5173\u914d\u7f6e\u4e0b\u6ca1\u6709\u53ef\u67e5\u8be2\u7684\u6570\u636e\u8868",
            }

        queryable_columns_map = self.field_permission_service.get_queryable_columns_map(
            db,
            queryable_tables,
        )
        queryable_profiles = self._build_table_profiles(
            [
                {
                    "table_name": table_name,
                    "table_comment": option_comment_map.get(table_name, ""),
                }
                for table_name in queryable_tables
            ],
            table_columns_map=queryable_columns_map,
        )
        vector_scores = self.vector_service.search_tables(
            db,
            question,
            candidate_tables=queryable_tables,
            top_k=max(30, len(queryable_tables)),
            candidate_profiles={name: queryable_profiles.get(name, "") for name in queryable_tables},
            route_kb_id=int(settings.TABLE_ROUTE_KB_ID or 0),
        )
        keyword_scores = self._score_table_name_candidates(question, queryable_tables)
        profile_scores = self._score_table_profile_candidates(question, queryable_profiles)

        final_scores: dict[str, float] = {}
        for table_name in queryable_tables:
            semantic_score = float(vector_scores.get(table_name, 0.0))
            keyword_score = float(keyword_scores.get(table_name, 0.0))
            profile_score = float(profile_scores.get(table_name, 0.0))
            # 混合检索核心：先用向量语义召回候选表，再叠加关键词精确分与注释语义分做精排。
            # 这样能在大表规模下保持召回，同时避免只靠向量导致的误命中。
            total_score = round(semantic_score * 10.0 + keyword_score + profile_score * 2.0, 6)
            if total_score > 0:
                final_scores[table_name] = total_score

        if not final_scores:
            return {
                "mode": "no_signal",
                "candidates": [],
                "scores": {},
                "clarify_question": "\u8def\u7531\u4fe1\u53f7\u8f83\u5f31\uff0c\u8bf7\u8865\u5145\u66f4\u5177\u4f53\u7684\u4e1a\u52a1\u5bf9\u8c61\u6216\u7b5b\u9009\u6761\u4ef6",
            }
        ranked = sorted(final_scores.keys(), key=lambda t: (-final_scores.get(t, 0.0), t))
        # 扩大 LLM 的候选池：既然向量和 token 的“死板”容易引发同义词鸿沟，
        # 在这阶段我们彻底放权，把有效候选池拉大到 150 张表（基本覆盖全库）。
        # 这就相当于让大模型直接作为“第一关”，利用大模型自身庞大的常识来识别表意映射。
        config_top_k = int(settings.TABLE_ROUTE_MAX_CANDIDATES)
        effective_top_k = max(150, config_top_k)
        top_k = min(effective_top_k, len(ranked))
        top_candidates = ranked[:top_k]
        _console_logger.info(
            "[route] top_candidates=%s scores=%s",
            json.dumps(top_candidates, ensure_ascii=False),
            json.dumps(
                {t: final_scores.get(t, 0.0) for t in top_candidates},
                ensure_ascii=False,
            ),
        )
        best_table = self._llm_select_best_table(
            question,
            top_candidates,
            table_comment_map=option_comment_map,
            table_columns_map=queryable_columns_map,
        )
        _console_logger.info(
            "[route] llm_selected=%s (from %s)",
            best_table,
            json.dumps(top_candidates, ensure_ascii=False),
        )
        return {
            "mode": "single",
            "candidates": [best_table],
            "scores": final_scores,
            "clarify_question": "",
        }

    def _llm_select_best_table(
        self,
        question: str,
        candidates: list[str],
        *,
        table_comment_map: dict[str, str],
        table_columns_map: dict[str, set[str]] | None = None,
    ) -> str:
        """让 LLM 从 Top-K 候选表中基于结构化描述选出最合适的一张。"""
        if not candidates:
            return ""
        if len(candidates) <= 1:
            return candidates[0]

        model = self._get_model()
        if model is None:
            return candidates[0]

        # 构建结构化的候选表描述，让 LLM 能清晰区分表注释和字段
        info_lines: list[str] = []
        for table_name in candidates:
            comment = table_comment_map.get(table_name, "").strip()
            label = f"{table_name}（{comment}）" if comment else table_name
            columns = sorted(
                str(c).strip()
                for c in (table_columns_map or {}).get(table_name, set())
                if str(c).strip()
            )
            # 只展示前 15 个字段名，避免过长干扰判断
            if len(columns) > 15:
                columns = columns[:15] + [f"...共{len(columns)}个字段"]
            columns_text = ", ".join(columns) if columns else "（无可用字段）"
            info_lines.append(f"- {label}\n  字段：{columns_text}")

        candidates_info = "\n".join(info_lines)
        chain = _TABLE_SELECTION_PROMPT | model | StrOutputParser()
        try:
            selected = str(
                chain.invoke(
                    {
                        "question": question,
                        "candidates_info": candidates_info,
                    }
                )
            ).strip().strip("`").strip('"')
        except Exception:  # noqa: BLE001
            _console_logger.exception("table selection LLM invoke failed")
            return candidates[0]

        normalized_lookup = {
            str(name).strip().lower(): name for name in candidates if str(name).strip()
        }
        normalized_selected = str(selected).strip().lower()
        if normalized_selected in normalized_lookup:
            return normalized_lookup[normalized_selected]

        for key, table_name in normalized_lookup.items():
            if key and key in normalized_selected:
                return table_name
        return candidates[0]

    @classmethod
    def _score_table_name_candidates(cls, question: str, table_names: list[str]) -> dict[str, float]:
        question_text = str(question or "").lower()
        question_tokens = cls._build_search_tokens(question_text, max_tokens=320)
        scores: dict[str, float] = {}
        for table_name in table_names:
            normalized_table = str(table_name or "").strip().lower()
            if not normalized_table:
                continue

            score = 0.0
            if normalized_table in question_text:
                score += 2.0

            for token in cls._build_search_tokens(normalized_table, max_tokens=64):
                if token in question_tokens:
                    score += 0.85
            scores[table_name] = round(score, 6)
        return scores

    @staticmethod
    def _normalize_table_list(tables) -> list[str]:
        """把输入转换成去重后的表名列表。"""
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
    def _expand_select_star(sql: str, table_columns_map: dict[str, set[str]]) -> str:
        """将 `SELECT *` 展开成显式字段，避免超出字段权限范围。"""
        sql_text = str(sql or "").strip().rstrip(";")
        if not sql_text:
            return "SELECT 1;"
        try:
            tree = parse_one(sql_text, read="mysql")
        except Exception:  # noqa: BLE001
            return sql_text + ";"
        if not isinstance(tree, exp.Select):
            return sql_text + ";"
        normalized_table_columns_map: dict[str, list[str]] = {}
        for table_name, columns in (table_columns_map or {}).items():
            normalized_table = Text2SQLValidatorService.normalize_table_identifier(table_name)
            if not normalized_table:
                continue
            normalized_table_columns_map[normalized_table] = sorted(
                [str(column) for column in (columns or set()) if str(column).strip()]
            )
        alias_map = Text2SQLValidatorService.build_alias_map(tree)
        normalized_alias_map = {
            Text2SQLValidatorService.normalize_identifier(alias): str(real_table)
            for alias, real_table in alias_map.items()
            if alias and real_table
        }
        table_order: list[tuple[str, str]] = []
        seen_tables: set[str] = set()
        for table in tree.find_all(exp.Table):
            if not table.name:
                continue
            normalized_table = Text2SQLValidatorService.normalize_table_identifier(str(table.name))
            if not normalized_table or normalized_table in seen_tables:
                continue
            seen_tables.add(normalized_table)
            qualifier = str(table.alias_or_name or table.name)
            table_order.append((normalized_table, qualifier))
        replaced = False
        expanded_expressions: list[exp.Expression] = []
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
        if replaced and expanded_expressions:
            tree.set("expressions", expanded_expressions)
        normalized_sql = tree.sql(dialect="mysql").strip().rstrip(";")
        return normalized_sql + ";"

    @staticmethod
    def _is_statistical_query(sql_text: str, tree: exp.Expression | None) -> bool:
        """判断 SQL 是否属于统计聚合查询。"""
        if tree is not None:
            if tree.args.get("group") is not None or tree.args.get("having") is not None:
                return True
            if any(tree.find(func_type) is not None for func_type in (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
                return True
        return bool(
            re.search(
                r"\b(count|sum|avg|min|max)\s*\(|\bgroup\s+by\b|\bhaving\b",
                sql_text,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _strip_top_level_limit(sql_text: str, tree: exp.Expression | None) -> str:
        """移除顶层 LIMIT，供统计查询回退使用。"""
        if tree is not None and tree.args.get("limit") is not None:
            copied = tree.copy()
            copied.set("limit", None)
            return copied.sql(dialect="mysql").strip().rstrip(";")
        return re.sub(
            r"\s+limit\s+\d+\s*(,\s*\d+)?\s*$",
            "",
            sql_text,
            flags=re.IGNORECASE,
        ).strip()

    @classmethod
    def _ensure_limit(cls, sql: str) -> str:
        """为明细查询补充默认 LIMIT，统计查询保持原样。"""
        sql_text = str(sql or "").strip().rstrip(";")
        if not sql_text:
            return f"SELECT 1 LIMIT {int(settings.TEXT2SQL_MAX_ROWS)};"
        tree: exp.Expression | None
        try:
            tree = parse_one(sql_text, read="mysql")
        except Exception:  # noqa: BLE001
            tree = None
        if cls._is_statistical_query(sql_text, tree):
            sql_without_limit = cls._strip_top_level_limit(sql_text, tree)
            return (sql_without_limit or sql_text).rstrip(";") + ";"
        if tree is not None and tree.args.get("limit") is not None:
            return tree.sql(dialect="mysql").strip().rstrip(";") + ";"
        if re.search(r"\blimit\b", sql_text, flags=re.IGNORECASE):
            return sql_text + ";"
        return f"{sql_text} LIMIT {int(settings.TEXT2SQL_MAX_ROWS)};"

    @staticmethod
    def _truncate_text(value: str | None, max_len: int) -> str:
        """截断长文本，避免日志过长。"""
        text = str(value or "")
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    @classmethod
    def _sample_rows_for_log(cls, rows: list[dict], max_rows: int = 3) -> list[dict]:
        """抽样部分结果行用于日志打印。"""
        sampled: list[dict] = []
        for row in rows[:max_rows]:
            sampled.append({str(k): cls._truncate_text(str(v), 80) for k, v in row.items()})
        return sampled

    def _get_model(self) -> ChatOpenAI | None:
        """按当前配置返回可复用的大模型客户端。"""
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
