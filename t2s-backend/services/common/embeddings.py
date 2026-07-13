from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from core.config import settings
from core.url_utils import normalize_embedding_base_url
from services.common.custom_e5_embeddings import CustomE5Embeddings
from services.common.model_config_service import MODEL_KIND_EMBEDDING, model_config_service


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class DeterministicEmbeddings:
    """离线兜底向量器，用确定性哈希生成可复现向量。"""

    def __init__(self, dim: int) -> None:
        self.dim = int(dim)

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        if self.dim <= 0:
            return vec

        tokens = re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", str(text or "").lower())
        if not tokens:
            tokens = [str(text or "").lower()]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(0, len(digest), 2):
                number = int.from_bytes(digest[index : index + 2], "big")
                vec[number % self.dim] += 1.0

        norm = math.sqrt(sum(value * value for value in vec))
        if norm <= 0:
            return vec
        return [value / norm for value in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


_embedding_instance: EmbeddingProvider | None = None
_embedding_cache_key = ""
_embedding_vector_dim: int | None = None
_embedding_vector_dim_cache_key = ""


def reset_embeddings() -> None:
    global _embedding_instance, _embedding_cache_key, _embedding_vector_dim, _embedding_vector_dim_cache_key
    _embedding_instance = None
    _embedding_cache_key = ""
    _embedding_vector_dim = None
    _embedding_vector_dim_cache_key = ""


def get_embedding_vector_dim(db=None) -> int:
    global _embedding_vector_dim, _embedding_vector_dim_cache_key

    runtime = model_config_service.get_active_runtime_config(MODEL_KIND_EMBEDDING, db=db)
    if runtime is not None and runtime.vector_dim:
        return int(runtime.vector_dim)
    if runtime is not None:
        cache_key = runtime.cache_key
        if _embedding_vector_dim is not None and _embedding_vector_dim_cache_key == cache_key:
            return int(_embedding_vector_dim)

        vector = get_embeddings(db).embed_query("dimension probe")
        dim = len(vector or [])
        if dim <= 0:
            raise RuntimeError("无法自动检测 Embedding 维度，请检查模型配置")
        _embedding_vector_dim = int(dim)
        _embedding_vector_dim_cache_key = cache_key
        return int(_embedding_vector_dim)
    return int(settings.ES_VECTOR_DIM)


def get_active_embedding_model_name(db=None) -> str | None:
    return model_config_service.get_active_model_name(MODEL_KIND_EMBEDDING, db=db)


def get_embeddings(db=None) -> EmbeddingProvider:
    global _embedding_instance, _embedding_cache_key

    runtime = model_config_service.get_active_runtime_config(MODEL_KIND_EMBEDDING, db=db)
    if runtime is not None:
        cache_key = runtime.cache_key
        if _embedding_instance is not None and _embedding_cache_key == cache_key:
            return _embedding_instance
        _embedding_instance = CustomE5Embeddings(
            api_base=normalize_embedding_base_url(runtime.base_url),
            api_key=runtime.api_key,
            model=runtime.model_name,
            timeout=int(runtime.timeout_seconds),
            batch_size=int(runtime.batch_size or 32),
            verify_ssl=bool(runtime.verify_ssl),
            ca_bundle=runtime.ca_bundle or None,
            max_retries=int(runtime.max_retries),
            retry_backoff_seconds=float(runtime.retry_backoff_seconds),
            trust_env=bool(runtime.trust_env),
        )
        _embedding_cache_key = cache_key
        return _embedding_instance

    cache_key = f"deterministic|{int(settings.ES_VECTOR_DIM)}"
    if _embedding_instance is not None and _embedding_cache_key == cache_key:
        return _embedding_instance
    _embedding_instance = DeterministicEmbeddings(dim=int(settings.ES_VECTOR_DIM))
    _embedding_cache_key = cache_key
    return _embedding_instance
