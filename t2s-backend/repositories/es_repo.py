from __future__ import annotations

import logging
from typing import Any

from elasticsearch import Elasticsearch, helpers

from core.config import settings
from core.es_index_name import is_valid_index_name

logger = logging.getLogger(__name__)


class ElasticsearchRepository:
    def __init__(self) -> None:
        self.client = Elasticsearch(
            settings.EFFECTIVE_ES_URL,
            request_timeout=settings.ES_REQUEST_TIMEOUT_SECONDS,
        )

    @staticmethod
    def _resolve_index_name(index_name: str | None) -> str:
        name = str(index_name or settings.ES_INDEX_NAME).strip()
        if not is_valid_index_name(name):
            raise ValueError(f"Invalid Elasticsearch index name: {name!r}")
        return name

    @staticmethod
    def _resolve_vector_dim(vector_dim: int | None) -> int:
        dim = int(vector_dim or settings.ES_VECTOR_DIM)
        if dim <= 0:
            raise ValueError("ES vector dim must be greater than 0")
        return dim

    def ensure_index(self, *, index_name: str | None = None, vector_dim: int | None = None) -> None:
        name = self._resolve_index_name(index_name)
        dim = self._resolve_vector_dim(vector_dim)

        if self.client.indices.exists(index=name):
            mapping = self.client.indices.get_mapping(index=name)
            properties = mapping[name]["mappings"].get("properties", {})
            field_dim = properties.get("embedding", {}).get("dims")
            if int(field_dim or 0) != dim:
                raise ValueError(
                    f"Elasticsearch index '{name}' vector dim mismatch: "
                    f"expected {dim}, got {field_dim}"
                )
            return

        mappings = {
            "properties": {
                "chunk_id": {"type": "long"},
                "kb_id": {"type": "long"},
                "file_id": {"type": "long"},
                "text": {"type": "text", "analyzer": "standard"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": dim,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        }
        self.client.indices.create(index=name, mappings=mappings)
        logger.info("created Elasticsearch index: %s, vector_dim=%s", name, dim)

    def insert_chunks(
        self,
        rows: list[dict[str, Any]],
        *,
        index_name: str | None = None,
        vector_dim: int | None = None,
    ) -> None:
        if not rows:
            return

        name = self._resolve_index_name(index_name)
        self.ensure_index(index_name=name, vector_dim=vector_dim)

        actions: list[dict[str, Any]] = []
        for row in rows:
            chunk_id = row.get("chunk_id")
            if chunk_id is None:
                raise ValueError("chunk_id is required for Elasticsearch indexing")
            actions.append(
                {
                    "_op_type": "index",
                    "_index": name,
                    "_id": str(chunk_id),
                    "_source": row,
                }
            )

        helpers.bulk(
            self.client,
            actions,
            raise_on_error=True,
            request_timeout=settings.ES_REQUEST_TIMEOUT_SECONDS,
        )
        self.client.indices.refresh(index=name)

    def delete_chunks_by_file_id(
        self,
        file_id: int,
        *,
        index_name: str | None = None,
        vector_dim: int | None = None,
    ) -> None:
        name = self._resolve_index_name(index_name)
        if not self.client.indices.exists(index=name):
            return

        self.client.delete_by_query(
            index=name,
            query={"term": {"file_id": int(file_id)}},
            refresh=True,
            conflicts="proceed",
        )

    def delete_chunks_by_kb_id(
        self,
        kb_id: int,
        *,
        index_name: str | None = None,
        vector_dim: int | None = None,
    ) -> None:
        name = self._resolve_index_name(index_name)
        if not self.client.indices.exists(index=name):
            return

        self.client.delete_by_query(
            index=name,
            query={"term": {"kb_id": int(kb_id)}},
            refresh=True,
            conflicts="proceed",
        )

    def delete_index(self, index_name: str | None) -> None:
        name = self._resolve_index_name(index_name)
        if self.client.indices.exists(index=name):
            self.client.indices.delete(index=name)

    def search_chunks(
        self,
        *,
        index_name: str | None = None,
        vector_dim: int | None = None,
        kb_id: int,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        name = self._resolve_index_name(index_name)
        dim = self._resolve_vector_dim(vector_dim)
        if len(query_vector) != dim:
            raise ValueError(
                f"query vector dim mismatch: expected={dim}, actual={len(query_vector)}"
            )

        if not self.client.indices.exists(index=name):
            return []

        top_k = max(1, int(top_k))
        num_candidates = max(
            top_k,
            top_k * 10,
            int(settings.ES_KNN_NUM_CANDIDATES),
        )

        response = self.client.search(
            index=name,
            knn={
                "field": "embedding",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": num_candidates,
                "filter": {"term": {"kb_id": int(kb_id)}},
            },
            size=top_k,
            source=["chunk_id", "kb_id", "file_id", "text"],
        )

        payload: list[dict[str, Any]] = []
        for hit in response["hits"]["hits"]:
            source = hit.get("_source", {})
            cosine_score = max(-1.0, min(1.0, 2.0 * float(hit.get("_score", 0.0)) - 1.0))
            payload.append(
                {
                    "score": cosine_score,
                    "chunk_id": source.get("chunk_id"),
                    "kb_id": source.get("kb_id"),
                    "file_id": source.get("file_id"),
                    "text": source.get("text"),
                }
            )
        return payload


es_repo = ElasticsearchRepository()
