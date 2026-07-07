"""URL normalization helpers for model API endpoints."""
from __future__ import annotations


def normalize_llm_base_url(url: str) -> str:
    """Strip common chat/completions suffixes from an OpenAI-compatible base URL."""
    value = str(url or "").strip().rstrip("/")
    for suffix in ("/chat/completions", "/chat", "/completions"):
        if value.lower().endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value.rstrip("/")


def normalize_embedding_base_url(url: str) -> str:
    """Strip a trailing embeddings endpoint; callers append it as needed."""
    value = str(url or "").strip().rstrip("/")
    if value.lower().endswith("/embeddings"):
        value = value[: -len("/embeddings")]
    return value.rstrip("/")


def normalize_rerank_base_url(url: str) -> str:
    """Strip common rerank endpoint suffixes; callers append /v1/rerank."""
    value = str(url or "").strip().rstrip("/")
    for suffix in ("/v1/rerank", "/rerank"):
        if value.lower().endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value.rstrip("/")
