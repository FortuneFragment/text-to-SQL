from __future__ import annotations

from dataclasses import dataclass
import os
import re
import tempfile

from sqlalchemy.orm import Session

from core.config import settings
from models.document_chunk import DocumentChunk
from models.knowledge_base import KnowledgeBase
from models.knowledge_file import KnowledgeFile
from repositories.knowledge_file_repo import KnowledgeFileRepository
from repositories.es_repo import es_repo
from repositories.minio_repo import minio_repo
from services.embeddings import get_embedding_vector_dim, get_embeddings


_TEXT_EXTENSIONS = {
    "txt",
    "md",
    "markdown",
    "csv",
    "json",
    "yaml",
    "yml",
    "sql",
    "log",
    "tsv",
}

_unstructured_partition = None
_unstructured_checked = False


def _get_unstructured_partition():
    global _unstructured_checked, _unstructured_partition

    if _unstructured_checked:
        return _unstructured_partition

    _unstructured_checked = True
    try:
        from unstructured.partition.auto import partition
    except Exception:  # noqa: BLE001
        _unstructured_partition = None
    else:
        _unstructured_partition = partition

    return _unstructured_partition


@dataclass
class ChunkPlan:
    chunk_size: int
    chunk_overlap: int


class RAGService:
    def _build_chunk_plan(self, kb: KnowledgeBase, file_entity: KnowledgeFile) -> ChunkPlan:
        chunk_size = int(file_entity.custom_chunk_size or kb.default_chunk_size)
        chunk_overlap = int(file_entity.custom_chunk_overlap or kb.default_chunk_overlap)

        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

        return ChunkPlan(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    @staticmethod
    def _decode_bytes(raw: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")

    def _extract_text(self, file_entity: KnowledgeFile, raw: bytes) -> str:
        ext = str(file_entity.file_type or "").lower().strip(".")
        text = self._decode_bytes(raw)

        if ext in _TEXT_EXTENSIONS:
            return text

        partition = _get_unstructured_partition()
        if partition is not None:
            suffix = f".{ext}" if ext else ""
            temp_path = ""
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                    temp_file.write(raw)
                    temp_path = temp_file.name
                elements = partition(filename=temp_path, strategy="auto")
                extracted = "\n\n".join(str(item) for item in elements if str(item).strip())
                if extracted.strip():
                    return extracted
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

        # For unknown/binary formats, try a soft fallback decode. If mostly unreadable, fail fast.
        cleaned = re.sub(r"\s+", "", text)
        if not cleaned:
            raise ValueError(
                f"Unsupported or unreadable file type '{ext}'. "
                "Please upload text-like files, or install optional parser dependency `unstructured`."
            )
        printable_ratio = sum(ch.isprintable() for ch in cleaned) / max(1, len(cleaned))
        if printable_ratio < 0.8:
            raise ValueError(
                f"File '{file_entity.file_name}' contains unsupported binary content. "
                "Please convert to a text-readable format before uploading."
            )
        return text

    @staticmethod
    def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
        source = str(text or "").replace("\r\n", "\n").strip()
        if not source:
            return []

        if len(source) <= chunk_size:
            return [source]

        step = chunk_size - chunk_overlap
        chunks: list[str] = []
        start = 0
        length = len(source)

        while start < length:
            end = min(length, start + chunk_size)
            piece = source[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= length:
                break
            start += step

        return chunks

    def process_and_embed_file(
        self,
        db: Session,
        *,
        file_entity: KnowledgeFile,
        kb_entity: KnowledgeBase,
    ) -> dict:
        chunk_plan = self._build_chunk_plan(kb_entity, file_entity)
        raw = minio_repo.get_file_bytes(file_entity.minio_object_name)
        text = self._extract_text(file_entity, raw)
        chunks = self._split_text(text, chunk_plan.chunk_size, chunk_plan.chunk_overlap)

        if not chunks:
            raise ValueError("Document content is empty after preprocessing")

        repo = KnowledgeFileRepository(db)
        chunk_entities = [
            DocumentChunk(
                kb_id=file_entity.kb_id,
                file_id=file_entity.id,
                chunk_index=index,
                content=content,
                char_count=len(content),
            )
            for index, content in enumerate(chunks)
        ]
        saved_chunks = repo.bulk_create_chunks(chunk_entities)

        embeddings = get_embeddings(db).embed_documents([item.content for item in saved_chunks])
        if not embeddings:
            raise ValueError("Embedding generation returned empty vectors")
        if len(embeddings) != len(saved_chunks):
            raise ValueError(
                "Embedding provider returned an unexpected vector count: "
                f"expected {len(saved_chunks)}, got {len(embeddings)}"
            )

        vector_dim = int(get_embedding_vector_dim(db))
        actual_dim = len(embeddings[0])
        for vector in embeddings:
            if len(vector) != actual_dim:
                raise ValueError(
                    f"Embedding provider returned inconsistent dims: expected {actual_dim}, got {len(vector)}"
                )
        if actual_dim != vector_dim:
            raise ValueError(
                "Embedding vector dim mismatch with configuration: "
                f"configured vector_dim={vector_dim}, embedding output={actual_dim}. "
                "Please align vector_dim with the selected embedding model."
            )

        rows = [
            {
                "chunk_id": int(chunk.id),
                "kb_id": int(chunk.kb_id),
                "file_id": int(chunk.file_id),
                "text": chunk.content,
                "embedding": vector,
            }
            for chunk, vector in zip(saved_chunks, embeddings)
        ]

        es_repo.insert_chunks(
            rows,
            index_name=kb_entity.collection_name,
            vector_dim=vector_dim,
        )

        return {
            "chunk_count": len(saved_chunks),
            "chunk_size": chunk_plan.chunk_size,
            "chunk_overlap": chunk_plan.chunk_overlap,
            "collection_name": kb_entity.collection_name,
        }


rag_service = RAGService()
