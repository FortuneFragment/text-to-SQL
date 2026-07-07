from __future__ import annotations

import pytest
import requests

from services.custom_e5_embeddings import CustomE5Embeddings


class DummyResponse:
    def __init__(self, body: dict) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.body


def test_embed_query_passes_ssl_and_proxy_options():
    embedder = CustomE5Embeddings(
        api_base="https://example.com/v1",
        api_key="secret",
        model="e5",
        verify_ssl=False,
        max_retries=0,
        trust_env=False,
    )
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return DummyResponse({"data": [{"embedding": [0.1, 0.2]}]})

    embedder.session.post = fake_post

    assert embedder.embed_query("hello") == [0.1, 0.2]
    assert captured["url"] == "https://example.com/v1/embeddings"
    assert captured["verify"] is False
    assert embedder.session.trust_env is False
    assert captured["headers"]["Authorization"] == "Bearer secret"


def test_embed_query_wraps_ssl_errors():
    embedder = CustomE5Embeddings(
        api_base="https://example.com/v1/embeddings",
        api_key="",
        model="e5",
        max_retries=0,
    )

    def fake_post(*args, **kwargs):
        raise requests.exceptions.SSLError("EOF occurred in violation of protocol")

    embedder.session.post = fake_post

    with pytest.raises(RuntimeError, match="SSL handshake failed"):
        embedder.embed_query("hello")


def test_embed_documents_splits_requests_by_batch_size():
    embedder = CustomE5Embeddings(
        api_base="https://example.com/v1",
        api_key="",
        model="e5",
        batch_size=2,
        max_retries=0,
    )
    batches = []

    def fake_post(url, **kwargs):
        batch = list(kwargs["json"]["input"])
        batches.append(batch)
        return DummyResponse({"data": [{"embedding": [float(ord(item) - 96)]} for item in batch]})

    embedder.session.post = fake_post

    vectors = embedder.embed_documents(["a", "b", "c", "d", "e"])

    assert batches == [["a", "b"], ["c", "d"], ["e"]]
    assert vectors == [[1.0], [2.0], [3.0], [4.0], [5.0]]