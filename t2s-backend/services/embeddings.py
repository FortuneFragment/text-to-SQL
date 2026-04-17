from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from core.config import settings
from services.custom_e5_embeddings import CustomE5Embeddings


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


def get_embeddings() -> EmbeddingProvider:
    global _embedding_instance
    if _embedding_instance is not None:
        return _embedding_instance

    base_url = str(settings.EMBEDDING_BASE_URL or "").strip()
    model = str(settings.EMBEDDING_MODEL or "").strip()

    if base_url and model:
        _embedding_instance = CustomE5Embeddings(
            api_base=base_url,
            api_key=str(settings.EMBEDDING_API_KEY or "").strip(),
            model=model,
            timeout=int(settings.EMBEDDING_TIMEOUT_SECONDS),
        )
    else:
        _embedding_instance = DeterministicEmbeddings(dim=int(settings.MILVUS_VECTOR_DIM))

    return _embedding_instance
