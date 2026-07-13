from __future__ import annotations

import hashlib
import json
import logging

from core.knowledge_policy import ProcessorType
from sqlalchemy.orm import Session
from core.domain_errors import (
    KnowledgeBaseConfigurationError,
)
from core.knowledge_policy import KnowledgeOperation
from services.common.knowledge_guard_service import knowledge_guard
from core.config import settings
from core.knowledge_usage import KB_USAGE_FEW_SHOT
from models.document_chunk import DocumentChunk
from models.knowledge_file import KnowledgeFile
from repositories.es_repo import es_repo
from repositories.knowledge_file_repo import KnowledgeFileRepository
from repositories.minio_repo import minio_repo
from repositories.text2sql_query_log_repo import Text2SQLQueryLogRepository
from services.common.embeddings import get_embedding_vector_dim, get_embeddings

_NO_EXAMPLES_TEXT = "(no historical examples)"
_logger = logging.getLogger("text2sql.few_shot")


class Text2SQLFewShotService:
    """Read and write few-shot examples from the isolated few-shot knowledge base."""

    def __init__(self, max_examples: int = 3, candidate_limit: int = 12) -> None:
        self._max_examples = max(1, int(max_examples))
        self._candidate_limit = max(self._max_examples, int(candidate_limit))

    @staticmethod
    def _is_feature_enabled() -> bool:
        return bool(getattr(settings, "TEXT2SQL_FEW_SHOT_ENABLED", False))

    @staticmethod
    def _safe_positive_int(value: object) -> int | None:
        try:
            parsed = int(value) if value is not None else 0
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        text = (value or "").strip().strip("`").strip('"').strip("[")
        if text.endswith("]"):
            text = text[:-1]
        if "." in text:
            text = text.split(".")[-1]
        return text.lower()

    @classmethod
    def _parse_selected_tables(cls, raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        tables: list[str] = []
        seen: set[str] = set()
        for item in parsed:
            value = str(item or "").strip()
            normalized = cls._normalize_identifier(value)
            if not value or not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tables.append(value)
        return tables

    @classmethod
    def _normalize_table_list(cls, values: list[str] | None) -> list[str]:
        tables: list[str] = []
        seen: set[str] = set()
        for item in values or []:
            value = str(item or "").strip()
            normalized = cls._normalize_identifier(value)
            if not value or not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tables.append(value)
        return tables

    def _resolve_few_shot_kb(
            self,
            db: Session,
            *,
            for_write: bool = False,
    ):
        operation = (
            KnowledgeOperation.FEW_SHOT_WRITE
            if for_write
            else KnowledgeOperation.FEW_SHOT_SEARCH
        )

        raw_configured_kb_id = getattr(
            settings,
            "FEW_SHOT_KB_ID",
            0,
        )

        configured_kb_id = self._safe_positive_int(raw_configured_kb_id)
        if configured_kb_id is None:
            raise KnowledgeBaseConfigurationError(
                "启用 Few-shot 前必须将 FEW_SHOT_KB_ID 配置为已存在的 Few-shot 知识库 ID，"
                f"当前值为：{raw_configured_kb_id!r}"
            )

        guard_ctx = knowledge_guard.resolve_kb_for_operation(
            db,
            configured_kb_id,
            operation,
        )
        return guard_ctx.kb

    @staticmethod
    def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
        source = str(text or "").strip()
        if not source:
            return []
        if len(source) <= chunk_size:
            return [source]

        step = max(1, int(chunk_size) - int(chunk_overlap))
        chunks: list[str] = []
        start = 0
        while start < len(source):
            piece = source[start : start + chunk_size].strip()
            if piece:
                chunks.append(piece)
            start += step
        return chunks

    @staticmethod
    def _build_example_text(
        *,
        log_id: int,
        question: str,
        sql: str,
        answer: str,
        selected_tables: list[str],
    ) -> str:
        lines = [
            "用途: text2sql few-shot",
            f"日志ID: {int(log_id)}",
            f"问题: {str(question or '').strip()}",
        ]
        if selected_tables:
            lines.append(f"候选表: {'、'.join(selected_tables)}")
        lines.extend(["SQL:", str(sql or "").strip()])
        if str(answer or "").strip():
            lines.extend(["回答:", str(answer or "").strip()])
        return "\n".join(line for line in lines if line is not None).strip()

    @staticmethod
    def _format_prompt_example(index: int, text: str) -> list[str]:
        lines = [f"示例{index}:"]
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("用途:") or line.startswith("日志ID:"):
                continue
            lines.append(f"  {line}")
        return lines

    def _insert_example_document(self, db: Session, *, kb, log_id: int, content: str) -> bool:
        raw = content.encode("utf-8")
        digest = hashlib.md5(raw, usedforsecurity=False).hexdigest()
        file_repo = KnowledgeFileRepository(db)
        kb_id = int(getattr(kb, "id", 0) or 0)
        if kb_id <= 0:
            return False
        if file_repo.check_exists_by_md5(kb_id, digest):
            return False

        object_name = f"few_shot/kb_{kb_id}/log_{int(log_id)}_{digest}.md"
        from core.knowledge_policy import ProcessorType
        file_entity = KnowledgeFile(
            kb_id=kb_id,
            file_name=f"few-shot-log-{int(log_id)}.md",
            file_type="md",
            file_size=len(raw),
            md5=digest,
            minio_bucket=minio_repo.bucket_name,
            minio_object_name=object_name,
            status=1,
            is_deleted=False,
            usage_snapshot=KB_USAGE_FEW_SHOT,
            processor_type=ProcessorType.FEW_SHOT.value,
            process_version=1,
        )
        created_file = file_repo.create_file(file_entity)

        try:
            minio_repo.upload_file_bytes(
                object_name,
                raw,
                content_type="text/markdown; charset=utf-8",
            )

            chunk_size = int(getattr(kb, "default_chunk_size", None) or settings.KB_CHUNK_SIZE)
            chunk_overlap = int(getattr(kb, "default_chunk_overlap", None) or settings.KB_CHUNK_OVERLAP)
            chunks = self._split_text(content, chunk_size, chunk_overlap)
            if not chunks:
                raise ValueError("few-shot example content is empty")

            chunk_entities = [
                DocumentChunk(
                    kb_id=kb_id,
                    file_id=int(created_file.id),
                    chunk_index=index,
                    content=chunk,
                    char_count=len(chunk),
                    usage_snapshot=KB_USAGE_FEW_SHOT,
                    processor_type=ProcessorType.FEW_SHOT.value,
                )
                for index, chunk in enumerate(chunks)
            ]
            saved_chunks = file_repo.bulk_create_chunks(chunk_entities)

            embeddings = get_embeddings(db).embed_documents([item.content for item in saved_chunks])
            if len(embeddings or []) != len(saved_chunks):
                raise ValueError("embedding provider returned unexpected vector count")

            vector_dim = int(get_embedding_vector_dim(db))
            rows = []
            for chunk, vector in zip(saved_chunks, embeddings):
                if len(vector) != vector_dim:
                    raise ValueError(
                        "Embedding vector dim mismatch with configuration: "
                        f"configured vector_dim={vector_dim}, embedding output={len(vector)}"
                    )
                rows.append(
                    {
                        "chunk_id": int(chunk.id),
                        "kb_id": kb_id,
                        "file_id": int(created_file.id),
                        "text": chunk.content,
                        "embedding": vector,
                        "usage_type": KB_USAGE_FEW_SHOT,
                        "processor_type": ProcessorType.FEW_SHOT.value,
                    }
                )

            es_repo.insert_chunks(
                rows,
                index_name=str(getattr(kb, "collection_name", "") or ""),
                vector_dim=vector_dim,
            )
            file_repo.update_status(int(created_file.id), status=2, error_msg=None)
            return True
        except Exception as exc:  # noqa: BLE001
            file_repo.update_status(int(created_file.id), status=3, error_msg=str(exc)[:1000])
            raise

    def upsert_feedback_example(
        self,
        db: Session,
        *,
        log_id: int,
        user_id: int,
        answer: str | None = None,
        question: str | None = None,
        sql: str | None = None,
        selected_tables: list[str] | None = None,
    ) -> bool:
        log = Text2SQLQueryLogRepository(db).get_success_log_for_owner(
            log_id=log_id,
            user_id=user_id,
        )
        if log is None:
            return False

        sql_text = str(getattr(log, "final_sql", "") or getattr(log, "generated_sql", "") or sql or "").strip()
        if not sql_text:
            return False

        trusted_tables = self._parse_selected_tables(getattr(log, "selected_tables", None))
        if not trusted_tables:
            trusted_tables = self._normalize_table_list(selected_tables)

        content = self._build_example_text(
            log_id=log_id,
            question=str(getattr(log, "question", "") or question or "").strip(),
            sql=sql_text,
            answer=str(answer or "").strip(),
            selected_tables=trusted_tables,
        )
        if not content:
            return False

        kb = self._resolve_few_shot_kb(db, for_write=True)
        if kb is None:
            return False
        return self._insert_example_document(db, kb=kb, log_id=log_id, content=content)

    def search_similar_examples(
        self,
        db: Session,
        question: str,
        *,
        table_names: list[str] | None = None,
        table_name: str | None = None,
    ) -> str:
        if not self._is_feature_enabled():
            return _NO_EXAMPLES_TEXT

        question_text = str(question or "").strip()
        if not question_text:
            return _NO_EXAMPLES_TEXT

        kb = self._resolve_few_shot_kb(db)
        if kb is None:
            return _NO_EXAMPLES_TEXT

        try:
            query_vector = list(get_embeddings(db).embed_query(question_text) or [])
            vector_dim = int(get_embedding_vector_dim(db))
            if len(query_vector) != vector_dim:
                _logger.warning(
                    "Few-shot vector dim mismatch: expected=%s actual=%s",
                    vector_dim,
                    len(query_vector),
                )
                return _NO_EXAMPLES_TEXT

            raw_hits = es_repo.search_chunks(
                index_name=str(getattr(kb, "collection_name", "") or ""),
                vector_dim=vector_dim,
                kb_id=int(getattr(kb, "id", 0) or 0),
                query_vector=query_vector,
                top_k=self._candidate_limit,
                expected_usage=KB_USAGE_FEW_SHOT,
                expected_processor_types=[ProcessorType.FEW_SHOT.value],
            )
        except Exception:  # noqa: BLE001
            _logger.exception("few-shot KB retrieval failed")
            return _NO_EXAMPLES_TEXT

        if not raw_hits:
            return _NO_EXAMPLES_TEXT

        normalized_tables = {
            self._normalize_identifier(item)
            for item in (table_names or [])
            if self._normalize_identifier(item)
        }
        if not normalized_tables and table_name:
            normalized = self._normalize_identifier(table_name)
            if normalized:
                normalized_tables.add(normalized)

        def table_overlap(hit: dict) -> int:
            if not normalized_tables:
                return 0
            text = str(hit.get("text") or "").lower()
            return sum(1 for table in normalized_tables if table and table in text)

        ranked_hits = sorted(
            raw_hits,
            key=lambda hit: (-table_overlap(hit), -float(hit.get("score") or 0.0)),
        )

        output_lines: list[str] = []
        used_texts: set[str] = set()
        example_index = 1
        for hit in ranked_hits:
            text = str(hit.get("text") or "").strip()
            if not text or text in used_texts:
                continue
            used_texts.add(text)
            output_lines.extend(self._format_prompt_example(example_index, text))
            example_index += 1
            if example_index > self._max_examples:
                break

        return "\n".join(output_lines) if output_lines else _NO_EXAMPLES_TEXT


few_shot_service = Text2SQLFewShotService()
