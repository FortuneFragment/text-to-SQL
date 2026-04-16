from __future__ import annotations

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from core.config import settings
from core.milvus_name import is_valid_collection_name


class MilvusRepository:
    def __init__(self) -> None:
        self.alias = "default"

    def _connect(self) -> None:
        connections.connect(
            alias=self.alias,
            host=settings.MILVUS_HOST,
            port=str(settings.MILVUS_PORT),
        )

    @staticmethod
    def _build_schema(vector_dim: int) -> CollectionSchema:
        return CollectionSchema(
            fields=[
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="chunk_id", dtype=DataType.INT64),
                FieldSchema(name="kb_id", dtype=DataType.INT64),
                FieldSchema(name="file_id", dtype=DataType.INT64),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=vector_dim),
            ],
            description="Text2SQL knowledge chunks",
        )

    def ensure_collection(
        self,
        *,
        collection_name: str,
        vector_dim: int,
    ) -> Collection:
        name = str(collection_name or "").strip()
        if not is_valid_collection_name(name):
            raise ValueError(
                "Invalid Milvus collection name: "
                f"'{name}'. The first character must be a letter or underscore, "
                "and only letters, digits, underscores are allowed."
            )

        self._connect()
        if not utility.has_collection(name, using=self.alias):
            schema = self._build_schema(vector_dim)
            collection = Collection(name=name, schema=schema, using=self.alias)
            collection.create_index(
                field_name="embedding",
                index_params={
                    "metric_type": "COSINE",
                    "index_type": "IVF_FLAT",
                    "params": {"nlist": 1024},
                },
            )
        collection = Collection(name=name, using=self.alias)
        embedding_field = next((field for field in collection.schema.fields if field.name == "embedding"), None)
        field_dim = (embedding_field.params or {}).get("dim") if embedding_field else None
        if int(field_dim or 0) != int(vector_dim):
            raise ValueError(
                f"Milvus collection '{name}' vector dim mismatch: "
                f"expected {vector_dim}, got {field_dim}"
            )
        collection.load()
        return collection

    def insert_chunks(
        self,
        rows: list[dict],
        *,
        collection_name: str,
        vector_dim: int,
    ) -> None:
        if not rows:
            return
        collection = self.ensure_collection(collection_name=collection_name, vector_dim=vector_dim)
        collection.insert(rows)
        collection.flush()

    def delete_chunks_by_file_id(self, file_id: int, *, collection_name: str, vector_dim: int) -> None:
        collection = self.ensure_collection(collection_name=collection_name, vector_dim=vector_dim)
        collection.delete(expr=f"file_id == {int(file_id)}")
        collection.flush()

    def delete_chunks_by_kb_id(self, kb_id: int, *, collection_name: str, vector_dim: int) -> None:
        collection = self.ensure_collection(collection_name=collection_name, vector_dim=vector_dim)
        collection.delete(expr=f"kb_id == {int(kb_id)}")
        collection.flush()

    def search_chunks(
        self,
        *,
        collection_name: str,
        vector_dim: int,
        kb_id: int,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        collection = self.ensure_collection(collection_name=collection_name, vector_dim=vector_dim)
        result = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=top_k,
            expr=f"kb_id == {int(kb_id)}",
            output_fields=["chunk_id", "kb_id", "file_id", "text"],
        )
        if not result:
            return []

        hits = result[0]
        payload: list[dict] = []
        for hit in hits:
            item = {
                "score": float(hit.score),
            }
            entity = getattr(hit, "entity", None)
            if entity is not None:
                item.update(
                    {
                        "chunk_id": entity.get("chunk_id"),
                        "kb_id": entity.get("kb_id"),
                        "file_id": entity.get("file_id"),
                        "text": entity.get("text"),
                    }
                )
            payload.append(item)
        return payload


milvus_repo = MilvusRepository()
