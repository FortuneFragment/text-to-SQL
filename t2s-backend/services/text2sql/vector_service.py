from __future__ import annotations

import logging
import math
import re
from collections import defaultdict

from sqlalchemy.orm import Session

from core.domain_errors import (
    KnowledgeBaseConfigurationError,
)
from core.knowledge_policy import KnowledgeOperation
from services.common.knowledge_guard_service import knowledge_guard
from core.knowledge_usage import KB_USAGE_TABLE_ROUTE
from models.knowledge_file import KnowledgeFile
from repositories.es_repo import es_repo
from services.common.embeddings import get_embedding_vector_dim, get_embeddings

_logger = logging.getLogger("text2sql.vector")
_TABLE_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")


class Text2SQLVectorService:
    """Provide table-level vector retrieval scores for routing."""

    def __init__(
            self,
            kb_id: int | None = 0,
    ):
        # 0 或 None 表示未启用固定的 table_route 知识库。
        if kb_id in (None, 0):
            self.kb_id = 0
            return

        parsed_kb_id = self._safe_positive_int(kb_id)

        if parsed_kb_id is None:
            raise KnowledgeBaseConfigurationError(
                "TABLE_ROUTE_KB_ID 必须是大于 0 的整数，"
                f"当前值为：{kb_id!r}"
            )

        self.kb_id = parsed_kb_id

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        text = (value or "").strip().strip("`").strip('"')
        if "." in text:
            text = text.split(".")[-1]
        return text.lower()

    @staticmethod
    def _contains_chinese(value: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in value)

    @classmethod
    def _tokenize_terms(cls, text: str, *, max_terms: int = 256) -> set[str]:
        terms: set[str] = set()
        for raw in _TABLE_TOKEN_PATTERN.findall(str(text or "").lower()):
            token = raw.strip().strip("_")
            if not token:
                continue

            if cls._contains_chinese(token):
                compact = token.replace("_", "")
                if compact:
                    terms.add(compact)
                if len(compact) >= 2:
                    # Use CJK 2-gram to avoid whole-sentence token mismatch.
                    max_grams = min(len(compact) - 1, 64)
                    for index in range(max_grams):
                        terms.add(compact[index : index + 2])
            else:
                for part in re.split(r"[_\s]+", token):
                    normalized_part = part.strip()
                    if len(normalized_part) >= 2:
                        terms.add(normalized_part)
                if len(token) >= 2:
                    terms.add(token)

            if len(terms) >= max_terms:
                break
        return terms

    @staticmethod
    def _normalize_similarity(value: float | int | None) -> float:
        score = float(value or 0.0)
        if score <= 0:
            return 0.0
        return max(0.0, min(1.0, score))

    @classmethod
    def _build_table_terms(cls, normalized_table: str, profile_text: str) -> set[str]:
        meaningful_terms = cls._tokenize_terms(normalized_table, max_terms=64)
        if profile_text:
            meaningful_terms.update(cls._tokenize_terms(profile_text, max_terms=192))
        if normalized_table:
            meaningful_terms.add(normalized_table)
        return meaningful_terms

    @staticmethod
    def _build_non_informative_terms(term_index: dict[str, set[str]], table_count: int) -> set[str]:
        """Filter out overly-shared tokens to reduce cross-table noise."""
        if table_count <= 1:
            return set()
        shared_threshold = max(2, int(math.ceil(float(table_count) * 0.35)))
        return {
            term
            for term, linked_tables in term_index.items()
            if len(linked_tables) >= shared_threshold
        }

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_positive_int(value: object) -> int | None:
        try:
            parsed = int(value) if value is not None else 0
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _load_file_name_lookup(db: Session, file_ids: set[int]) -> dict[int, str]:
        if not file_ids:
            return {}
        rows = (
            db.query(KnowledgeFile.id, KnowledgeFile.file_name)
            .filter(KnowledgeFile.id.in_(sorted(file_ids)))
            .all()
        )
        return {int(file_id): str(file_name or "") for file_id, file_name in rows}

    def _resolve_route_kb(
            self,
            db: Session,
            requested_kb_id: int | None = None,
    ) -> tuple[int, object | None]:
        # 调用方明确传入了 ID。
        if requested_kb_id not in (None, 0):
            explicit_kb_id = self._safe_positive_int(
                requested_kb_id
            )

            if explicit_kb_id is None:
                raise KnowledgeBaseConfigurationError(
                    "route_kb_id 必须是大于 0 的整数，"
                    f"当前值为：{requested_kb_id!r}"
                )

            guard_ctx = knowledge_guard.resolve_kb_for_operation(
                db,
                explicit_kb_id,
                KnowledgeOperation.TABLE_ROUTE_SEARCH,
            )
            return explicit_kb_id, guard_ctx.kb

        # 服务实例配置了固定知识库。
        if self.kb_id > 0:
            guard_ctx = knowledge_guard.resolve_kb_for_operation(
                db,
                self.kb_id,
                KnowledgeOperation.TABLE_ROUTE_SEARCH,
            )
            return self.kb_id, guard_ctx.kb

        return 0, None

    def _resolve_collection_name(self, db: Session, requested_kb_id: int | None = None) -> tuple[int, str]:
        active_kb_id, kb = self._resolve_route_kb(db, requested_kb_id=requested_kb_id)
        if kb is None:
            return 0, ""
        return active_kb_id, str(getattr(kb, "collection_name", "") or "").strip()

    def search_tables(
        self,
        db: Session,
        question: str,
        *,
        candidate_tables: list[str],
        top_k: int = 15,
        candidate_profiles: dict[str, str] | None = None,
        route_kb_id: int | None = None,
    ) -> dict[str, float]:
        question_text = str(question or "").strip()
        if not question_text or not candidate_tables:
            return {}

        active_kb_id, collection_name = self._resolve_collection_name(db, requested_kb_id=route_kb_id)
        if not collection_name or active_kb_id <= 0:
            _logger.warning(
                "Vector KB not found: active_kb_id=%s requested_kb_id=%s configured_kb_id=%s",
                active_kb_id,
                route_kb_id,
                self.kb_id,
            )
            return {}

        try:
            query_vector = list(get_embeddings(db).embed_query(question_text) or [])
            if not query_vector:
                return {}
            expected_dim = int(get_embedding_vector_dim(db))
            if len(query_vector) != expected_dim:
                _logger.warning(
                    "Vector dim mismatch for routing: expected=%s actual=%s",
                    expected_dim,
                    len(query_vector),
                )
                return {}

            query_limit = max(int(top_k) * 8, 40)
            raw_hits = es_repo.search_chunks(
                index_name=collection_name,
                vector_dim=expected_dim,
                kb_id=active_kb_id,
                query_vector=query_vector,
                top_k=query_limit,
                expected_usage=KB_USAGE_TABLE_ROUTE,
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Vector search failed for kb_id=%s requested_kb_id=%s",
                active_kb_id,
                route_kb_id,
            )
            return {}

        profile_lookup = {
            self._normalize_identifier(table_name): str(profile_text or "")
            for table_name, profile_text in (candidate_profiles or {}).items()
        }
        table_lookup: dict[str, str] = {}
        table_terms: dict[str, set[str]] = {}
        term_index: dict[str, set[str]] = defaultdict(set)
        for table_name in candidate_tables:
            normalized = self._normalize_identifier(table_name)
            if not normalized:
                continue
            table_lookup[normalized] = table_name
            profile_text = profile_lookup.get(normalized, "")
            terms = self._build_table_terms(normalized, profile_text)
            table_terms[normalized] = terms
            for term in terms:
                term_index[term].add(normalized)

        if not table_lookup:
            return {}
        non_informative_terms = self._build_non_informative_terms(term_index, len(table_lookup))
        table_terms_for_match: dict[str, set[str]] = {}
        for normalized_table, terms in table_terms.items():
            filtered_terms = {
                term
                for term in terms
                if term == normalized_table or term not in non_informative_terms
            }
            table_terms_for_match[normalized_table] = filtered_terms or terms

        file_ids: set[int] = set()
        for hit in raw_hits:
            file_id = self._safe_int(hit.get("file_id"))
            if file_id is not None and file_id > 0:
                file_ids.add(file_id)
        file_name_lookup = self._load_file_name_lookup(db, file_ids)

        score_max: dict[str, float] = {}
        score_sum: dict[str, float] = defaultdict(float)
        score_hits: dict[str, int] = defaultdict(int)

        for hit in raw_hits:
            hit_text = str(hit.get("text") or "")
            base_score = self._normalize_similarity(hit.get("score"))
            if base_score <= 0:
                continue

            source_parts = [hit_text]
            file_id = self._safe_int(hit.get("file_id"))
            if file_id is not None and file_id > 0:
                file_name = file_name_lookup.get(file_id, "")
                if file_name:
                    source_parts.append(file_name)
            source_text = " ".join(part for part in source_parts if part).strip()
            if not source_text:
                continue

            text_terms = self._tokenize_terms(source_text, max_terms=512)
            if not text_terms:
                continue
            informative_text_terms = {
                term
                for term in text_terms
                if term not in non_informative_terms
            }
            if not informative_text_terms:
                continue

            matched_tables: set[str] = set()
            for term in informative_text_terms:
                matched_tables.update(term_index.get(term, set()))
            if not matched_tables:
                continue
            # 一个片段同时命中过多表时，通常缺少区分度（如全量表清单/总览文档），应降权。
            diversity_penalty = 1.0
            if len(matched_tables) > 3:
                diversity_penalty = max(0.01, 3.0 / float(len(matched_tables)))

            for normalized_table in matched_tables:
                terms = table_terms_for_match.get(normalized_table, set())
                if not terms:
                    continue

                overlap = len(terms.intersection(informative_text_terms))
                if overlap <= 0:
                    continue

                if normalized_table in informative_text_terms:
                    factor = 1.0
                elif overlap >= 4:
                    factor = 0.85
                elif overlap >= 2:
                    factor = 0.72
                else:
                    factor = 0.56

                score = round(base_score * factor * diversity_penalty, 6)
                if score <= 0:
                    continue

                real_table = table_lookup.get(normalized_table)
                if not real_table:
                    continue
                score_max[real_table] = round(max(score_max.get(real_table, 0.0), score), 6)
                score_sum[real_table] = float(score_sum.get(real_table, 0.0)) + score
                score_hits[real_table] = int(score_hits.get(real_table, 0)) + 1

        blended_scores: dict[str, float] = {}
        for table_name, max_score in score_max.items():
            total_score = float(score_sum.get(table_name, 0.0))
            hit_count = int(score_hits.get(table_name, 0))
            extra_signal = max(0.0, total_score - float(max_score))
            blended = (
                float(max_score)
                + min(0.35, extra_signal * 0.3)
                + min(0.15, float(hit_count) * 0.03)
            )
            blended_scores[table_name] = round(max(0.0, min(1.0, blended)), 6)

        return blended_scores

