from __future__ import annotations

import logging
import re
from collections import defaultdict

from sqlalchemy.orm import Session

from core.config import settings
from models.knowledge_file import KnowledgeFile
from repositories.knowledge_base_repo import KnowledgeBaseRepository
from repositories.milvus_repo import milvus_repo
from services.embeddings import get_embeddings

_logger = logging.getLogger("text2sql.vector")
_TABLE_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")


class Text2SQLVectorService:
    """Text2SQL table-routing vector retrieval service."""

    def __init__(self, kb_id: int = 2):
        # Convention: knowledge base ID=2 is used for table-routing semantic retrieval.
        self.kb_id = int(kb_id)

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
    def _safe_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

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

    def _resolve_collection_name(self, db: Session) -> str:
        kb = KnowledgeBaseRepository(db).get_by_id(self.kb_id)
        if kb is None:
            return ""
        return str(kb.collection_name or "").strip()

    def search_tables(
        self,
        db: Session,
        question: str,
        *,
        candidate_tables: list[str],
        top_k: int = 15,
        candidate_profiles: dict[str, str] | None = None,
    ) -> dict[str, float]:
        question_text = str(question or "").strip()
        if not question_text or not candidate_tables:
            return {}

        collection_name = self._resolve_collection_name(db)
        if not collection_name:
            _logger.warning("Vector KB not found: kb_id=%s", self.kb_id)
            return {}

        try:
            query_vector = list(get_embeddings().embed_query(question_text) or [])
            if not query_vector:
                return {}
            expected_dim = int(settings.MILVUS_VECTOR_DIM)
            if len(query_vector) != expected_dim:
                _logger.warning(
                    "Vector dim mismatch for routing: expected=%s actual=%s",
                    expected_dim,
                    len(query_vector),
                )
                return {}

            query_limit = max(int(top_k) * 8, 40)
            raw_hits = milvus_repo.search_chunks(
                collection_name=collection_name,
                vector_dim=expected_dim,
                kb_id=self.kb_id,
                query_vector=query_vector,
                top_k=query_limit,
            )
        except Exception:  # noqa: BLE001
            _logger.exception("Vector search failed for kb_id=%s", self.kb_id)
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

        file_ids: set[int] = set()
        for hit in raw_hits:
            file_id = self._safe_int(hit.get("file_id"))
            if file_id is not None and file_id > 0:
                file_ids.add(file_id)
        file_name_lookup = self._load_file_name_lookup(db, file_ids)

        scores: dict[str, float] = {}
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

            matched_tables: set[str] = set()
            for term in text_terms:
                matched_tables.update(term_index.get(term, set()))
            if not matched_tables:
                continue

            for normalized_table in matched_tables:
                terms = table_terms.get(normalized_table, set())
                if not terms:
                    continue

                overlap = len(terms.intersection(text_terms))
                if overlap <= 0:
                    continue

                if normalized_table in text_terms:
                    factor = 1.0
                elif overlap >= 4:
                    factor = 0.85
                elif overlap >= 2:
                    factor = 0.72
                else:
                    factor = 0.56

                score = round(base_score * factor, 6)
                if score <= 0:
                    continue

                real_table = table_lookup.get(normalized_table)
                if not real_table:
                    continue
                scores[real_table] = round(max(scores.get(real_table, 0.0), score), 6)

        return scores
