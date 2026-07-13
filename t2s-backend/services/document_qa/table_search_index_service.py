from __future__ import annotations

import json
import logging
import re
from typing import Any

from core.config import settings
from core.es_index_name import is_valid_index_name
from repositories.es_repo import es_repo
from services.common.embeddings import get_embedding_vector_dim, get_embeddings

logger = logging.getLogger(__name__)

TREE_PATH_LIMIT = 2000
TREE_LEAF_LIMIT = 2000
MAX_EMBEDDING_TEXT_CHARS = 12000
RRF_RANK_CONSTANT = 60


class TableSearchIndexService:
    @staticmethod
    def table_index_name(collection_name: str) -> str:
        base = str(collection_name or settings.ES_INDEX_NAME).strip().lower()
        candidate = f"{base}-tables"
        if is_valid_index_name(candidate):
            return candidate
        candidate = re.sub(r"[^a-z0-9_-]+", "-", candidate).strip("-_")
        if not candidate or not is_valid_index_name(candidate):
            raise ValueError(f"Invalid table index name: {collection_name!r}")
        return candidate[:128]

    def ensure_index(self, *, index_name: str, vector_dim: int) -> None:
        client = es_repo.client
        properties = _table_index_properties(vector_dim)
        if client.indices.exists(index=index_name):
            mapping = client.indices.get_mapping(index=index_name)
            properties = mapping[index_name]["mappings"].get("properties", {})
            field_dim = properties.get("embedding", {}).get("dims")
            if int(field_dim or 0) != int(vector_dim):
                raise ValueError(
                    f"Elasticsearch table index '{index_name}' vector dim mismatch: "
                    f"expected {vector_dim}, got {field_dim}"
                )
            wanted = _table_index_properties(vector_dim)
            missing = {key: value for key, value in wanted.items() if key not in properties}
            if missing:
                client.indices.put_mapping(index=index_name, properties=missing)
            return

        client.indices.create(index=index_name, mappings={"properties": properties})
        logger.info("created table search index: %s, vector_dim=%s", index_name, vector_dim)

    def index_table(
        self,
        db,
        *,
        collection_name: str,
        artifact: dict[str, Any],
        tree_payload: dict[str, Any],
    ) -> None:
        index_name = self.table_index_name(collection_name)
        vector_dim = int(get_embedding_vector_dim(db))
        self.ensure_index(index_name=index_name, vector_dim=vector_dim)
        document = build_table_document(artifact=artifact, tree_payload=tree_payload)
        try:
            embedding = get_embeddings(db).embed_query(_truncate_embedding_text(document["search_text"]))
            if len(embedding) == vector_dim:
                document["embedding"] = embedding
            else:
                document["embedding_error"] = f"embedding_dim_mismatch: expected={vector_dim}, actual={len(embedding)}"
        except Exception as exc:  # noqa: BLE001
            document["embedding_error"] = f"{exc.__class__.__name__}: {exc}"
        es_repo.client.index(
            index=index_name,
            id=str(document["table_id"]),
            document=document,
            refresh=True,
            request_timeout=settings.ES_REQUEST_TIMEOUT_SECONDS,
        )

    def delete_by_file_id(self, *, collection_name: str, file_id: int) -> None:
        index_name = self.table_index_name(collection_name)
        client = es_repo.client
        if not client.indices.exists(index=index_name):
            return
        client.delete_by_query(
            index=index_name,
            query={"term": {"file_id": int(file_id)}},
            refresh=True,
            conflicts="proceed",
        )

    def delete_by_file_context(
        self,
        *,
        collection_name: str,
        kb_id: int,
        file_id: int,
    ) -> None:
        index_name = self.table_index_name(
            collection_name
        )

        client = es_repo.client

        if not client.indices.exists(
            index=index_name
        ):
            return

        client.delete_by_query(
            index=index_name,
            query={
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "kb_id": int(kb_id),
                            }
                        },
                        {
                            "term": {
                                "file_id": int(file_id),
                            }
                        },
                        {
                            "term": {
                                "usage_type":
                                    "table_semantic_tree",
                            }
                        },
                        {
                            "term": {
                                "processor_type":
                                    "table_semantic",
                            }
                        },
                    ]
                }
            },
            refresh=True,
            conflicts="proceed",
        )

    def get_table_document(self, *, collection_name: str, table_id: str) -> dict[str, Any] | None:
        index_name = self.table_index_name(collection_name)
        client = es_repo.client
        if not client.indices.exists(index=index_name):
            return None
        try:
            response = client.get(index=index_name, id=str(table_id))
        except Exception:  # noqa: BLE001
            return None
        return dict(response.get("_source") or {})

    def search(
        self,
        db,
        *,
        collection_name: str,
        kb_id: int,
        question: str,
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        index_name = self.table_index_name(collection_name)
        client = es_repo.client
        if not client.indices.exists(index=index_name):
            return []

        query = str(question or "").strip()
        if not query:
            return []

        safe_top_k = max(1, min(int(top_k), 50))
        semantic_hits: list[dict[str, Any]] = []
        try:
            vector_dim = int(get_embedding_vector_dim(db))
            query_vector = get_embeddings(db).embed_query(query)
            if len(query_vector) == vector_dim:
                semantic_hits = self._vector_search(
                    index_name=index_name,
                    kb_id=kb_id,
                    query_vector=query_vector,
                    top_k=safe_top_k,
                )
            else:
                logger.warning("table query vector dim mismatch: expected=%s actual=%s", vector_dim, len(query_vector))
        except Exception as exc:  # noqa: BLE001
            logger.warning("table vector search failed, fallback to text search: %s", exc)
        text_hits = self._text_search(index_name=index_name, kb_id=kb_id, question=query, top_k=safe_top_k)
        return _merge_hits(semantic_hits, text_hits, limit=safe_top_k)

    @staticmethod
    def _vector_search(*, index_name: str, kb_id: int, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        filters = [
            {"term": {"kb_id": int(kb_id)}},
            {"term": {"usage_type": "table_semantic_tree"}},
            {"term": {"processor_type": "table_semantic"}},
        ]
        response = es_repo.client.search(
            index=index_name,
            knn={
                "field": "embedding",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": max(top_k * 10, int(settings.ES_KNN_NUM_CANDIDATES)),
                "filter": filters,
            },
            size=top_k,
            source=True,
        )
        return [_hit_to_result(hit, score_scale="cosine") for hit in response["hits"]["hits"]]

    @staticmethod
    def _text_search(*, index_name: str, kb_id: int, question: str, top_k: int) -> list[dict[str, Any]]:
        filters = [
            {"term": {"kb_id": int(kb_id)}},
            {"term": {"usage_type": "table_semantic_tree"}},
            {"term": {"processor_type": "table_semantic"}},
        ]
        response = es_repo.client.search(
            index=index_name,
            query={
                "bool": {
                    "filter": filters,
                    "must": [
                        {
                            "multi_match": {
                                "query": question,
                                "fields": [
                                    "table_title^4",
                                    "summary_text^3",
                                    "candidate_fields^3",
                                    "tree_metric_names^3",
                                    "tree_path_text^5",
                                    "tree_leaf_text^3",
                                    "tree_search_text^2",
                                    "normalized_headers",
                                    "hierarchy_definition",
                                    "search_text",
                                ],
                            }
                        }
                    ],
                }
            },
            size=top_k,
            source=True,
        )
        return [_hit_to_result(hit, score_scale="text") for hit in response["hits"]["hits"]]


def _table_index_properties(vector_dim: int) -> dict[str, Any]:
    return {
        "doc_id": {"type": "keyword"},
        "kb_id": {"type": "long"},
        "file_id": {"type": "long"},
        "usage_type": {"type": "keyword"},
        "processor_type": {"type": "keyword"},
        "table_id": {"type": "keyword"},
        "table_title": {"type": "text", "analyzer": "standard", "fields": {"raw": {"type": "keyword"}}},
        "file_name": {"type": "keyword"},
        "sheet_name": {"type": "keyword"},
        "summary_text": {"type": "text", "analyzer": "standard"},
        "candidate_fields": {"type": "keyword"},
        "tree_metric_names": {"type": "keyword"},
        "tree_path_text": {"type": "text", "analyzer": "standard"},
        "tree_leaf_text": {"type": "text", "analyzer": "standard"},
        "tree_search_text": {"type": "text", "analyzer": "standard"},
        "normalized_headers": {"type": "text", "analyzer": "standard"},
        "hierarchy_definition": {"type": "text", "analyzer": "standard"},
        "search_text": {"type": "text", "analyzer": "standard"},
        "parse_mode": {"type": "keyword"},
        "large_table_reason": {"type": "text", "analyzer": "standard"},
        "embedding_error": {"type": "text", "analyzer": "standard"},
        "tree_object_name": {"type": "keyword"},
        "source_object_name": {"type": "keyword"},
        "normalized_object_name": {"type": "keyword"},
        "tree_object": {"type": "keyword"},
        "source_object": {"type": "keyword"},
        "xlsx_object": {"type": "keyword"},
        "row_count": {"type": "integer"},
        "column_count": {"type": "integer"},
        "embedding": {
            "type": "dense_vector",
            "dims": int(vector_dim),
            "index": True,
            "similarity": "cosine",
        },
    }


def build_tree_index_fields(tree: dict[str, Any]) -> dict[str, Any]:
    path_texts: list[str] = []
    leaf_texts: list[str] = []
    metric_names: list[str] = []

    def walk(node: Any, path: list[str]) -> None:
        if len(path_texts) >= TREE_PATH_LIMIT:
            return
        if isinstance(node, dict):
            if node and all(not isinstance(value, (dict, list)) for value in node.values()):
                _append_tree_index_record(
                    path=path,
                    data=node,
                    path_texts=path_texts,
                    leaf_texts=leaf_texts,
                    metric_names=metric_names,
                )
                return
            for key, value in node.items():
                key_text = str(key)
                metric_names.extend(_extract_metric_names_from_text(key_text))
                walk(value, [*path, key_text])
            return
        if isinstance(node, list):
            for index, value in enumerate(node, start=1):
                walk(value, [*path, f"第{index}项"])
            return
        _append_tree_index_record(
            path=path,
            data=node,
            path_texts=path_texts,
            leaf_texts=leaf_texts,
            metric_names=metric_names,
        )

    walk(tree, [])
    deduped_paths = _dedupe_strings(path_texts, limit=TREE_PATH_LIMIT)
    deduped_leafs = _dedupe_strings(leaf_texts, limit=TREE_LEAF_LIMIT)
    deduped_metrics = _dedupe_strings(metric_names, limit=300)
    tree_search_text = "\n".join(
        [
            "树路径：",
            *deduped_paths[:400],
            "树叶子数据：",
            *deduped_leafs[:400],
            "树指标：",
            "、".join(deduped_metrics),
        ]
    )
    return {
        "tree_path_text": deduped_paths,
        "tree_leaf_text": deduped_leafs,
        "tree_metric_names": deduped_metrics,
        "tree_search_text": tree_search_text,
    }


def _append_tree_index_record(
    *,
    path: list[str],
    data: Any,
    path_texts: list[str],
    leaf_texts: list[str],
    metric_names: list[str],
) -> None:
    path_text = " | ".join(path)
    leaf_text = _leaf_to_text(data)
    if path_text:
        path_texts.append(path_text)
        metric_names.extend(_extract_metric_names_from_text(path_text))
    if leaf_text:
        leaf_texts.append(leaf_text)
        metric_names.extend(_extract_metric_names_from_text(leaf_text))
    if isinstance(data, dict):
        for key in data.keys():
            metric_names.extend(_extract_metric_names_from_text(str(key)))


def _leaf_to_text(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{key}={item}" for key, item in value.items())
    return str(value)


def _extract_metric_names_from_text(text: str) -> list[str]:
    values: list[str] = []
    for part in re.split(r"[|;；,，:：=]+", str(text or "")):
        cleaned = part.strip()
        if not cleaned:
            continue
        values.append(cleaned)
        if " - " in cleaned:
            values.extend(item.strip() for item in cleaned.split(" - ") if item.strip())
    return [value for value in values if 1 < len(value) <= 100 and not re.fullmatch(r"[\d.\-]+", value)]


def _normalized_headers(*, parse_plan: dict[str, Any], candidate_fields: list[str]) -> str:
    payload = {
        "hierarchy_columns": parse_plan.get("hierarchy_columns", []),
        "value_columns": parse_plan.get("value_columns", candidate_fields),
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def _hierarchy_definition(*, parse_plan: dict[str, Any], coverage: Any) -> str:
    payload = {
        "table_range": parse_plan.get("table_range"),
        "title_ranges": parse_plan.get("title_ranges", []),
        "header_ranges": parse_plan.get("header_ranges", []),
        "data_row_range": parse_plan.get("data_row_range"),
        "hierarchy_columns": parse_plan.get("hierarchy_columns", []),
        "value_columns": parse_plan.get("value_columns", []),
        "hierarchy_fill_down": parse_plan.get("hierarchy_fill_down", parse_plan.get("fill_down")),
        "ignored_rows": parse_plan.get("ignored_rows", []),
        "row_paths": parse_plan.get("row_paths", []),
        "notes": parse_plan.get("notes", []),
        "coverage": coverage if isinstance(coverage, dict) else {},
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def build_table_document(*, artifact: dict[str, Any], tree_payload: dict[str, Any]) -> dict[str, Any]:
    candidate_fields = _string_list(tree_payload.get("candidate_fields")) or _string_list(artifact.get("candidate_fields"))
    tree_metric_names = _string_list(tree_payload.get("tree_metric_names")) or _string_list(artifact.get("tree_metric_names"))
    tree_path_text = _string_list(tree_payload.get("tree_path_text")) or _string_list(artifact.get("tree_path_text"))
    tree_fields = build_tree_index_fields(tree_payload.get("tree") if isinstance(tree_payload.get("tree"), dict) else {})
    if not tree_path_text:
        tree_path_text = _string_list(tree_fields.get("tree_path_text"))
    tree_leaf_text = _string_list(tree_fields.get("tree_leaf_text"))
    if not tree_metric_names:
        tree_metric_names = _string_list(tree_fields.get("tree_metric_names"))
    parse_plan = tree_payload.get("parse_plan") if isinstance(tree_payload.get("parse_plan"), dict) else {}
    normalized_headers = str(
        tree_payload.get("normalized_headers")
        or _normalized_headers(parse_plan=parse_plan, candidate_fields=candidate_fields)
    )
    hierarchy_definition = str(
        tree_payload.get("hierarchy_definition")
        or _hierarchy_definition(parse_plan=parse_plan, coverage=tree_payload.get("coverage"))
    )
    tree_search_text = str(tree_fields.get("tree_search_text") or "")
    search_text = "\n".join(
        [
            f"table_id: {artifact.get('table_id')}",
            f"表格标题: {artifact.get('table_title')}",
            f"文件: {artifact.get('file_name')}",
            f"工作表: {artifact.get('sheet_name')}",
            f"摘要: {artifact.get('summary_text')}",
            f"字段: {'、'.join(candidate_fields)}",
            f"指标: {'、'.join(tree_metric_names)}",
            "树路径:",
            "\n".join(tree_path_text[:TREE_PATH_LIMIT]),
            "树叶子数据:",
            "\n".join(tree_leaf_text[:400]),
            normalized_headers,
            hierarchy_definition,
            tree_search_text,
        ]
    )
    parse_mode = str(tree_payload.get("parse_mode") or parse_plan.get("source") or ("plan_based" if parse_plan else "heuristic"))
    source_object_name = str(tree_payload.get("source_object_name") or "")
    normalized_object_name = str(tree_payload.get("normalized_object_name") or "")
    tree_object_name = str(artifact.get("tree_object_name") or "")
    return {
        "doc_id": str(artifact.get("table_id")),
        "kb_id": int(artifact.get("kb_id") or 0),
        "file_id": int(artifact.get("file_id") or 0),
        "usage_type": "table_semantic_tree",
        "processor_type": "table_semantic",
        "table_id": str(artifact.get("table_id") or ""),
        "table_title": str(artifact.get("table_title") or ""),
        "file_name": str(artifact.get("file_name") or ""),
        "sheet_name": str(artifact.get("sheet_name") or ""),
        "summary_text": str(artifact.get("summary_text") or ""),
        "candidate_fields": candidate_fields,
        "tree_metric_names": tree_metric_names,
        "tree_path_text": tree_path_text[:TREE_PATH_LIMIT],
        "tree_leaf_text": tree_leaf_text[:TREE_LEAF_LIMIT],
        "tree_search_text": tree_search_text,
        "normalized_headers": normalized_headers,
        "hierarchy_definition": hierarchy_definition,
        "search_text": search_text,
        "parse_mode": parse_mode,
        "large_table_reason": str(tree_payload.get("large_table_reason") or ""),
        "embedding_error": "",
        "tree_object_name": tree_object_name,
        "source_object_name": source_object_name,
        "normalized_object_name": normalized_object_name,
        "tree_object": tree_object_name,
        "source_object": source_object_name,
        "xlsx_object": normalized_object_name,
        "row_count": int(artifact.get("row_count") or 0),
        "column_count": int(artifact.get("column_count") or 0),
    }


def _truncate_embedding_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if len(cleaned) <= MAX_EMBEDDING_TEXT_CHARS:
        return cleaned
    head_chars = int(MAX_EMBEDDING_TEXT_CHARS * 0.75)
    tail_chars = MAX_EMBEDDING_TEXT_CHARS - head_chars
    return f"{cleaned[:head_chars]}\n...\n{cleaned[-tail_chars:]}"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _hit_to_result(hit: dict[str, Any], *, score_scale: str) -> dict[str, Any]:
    source = dict(hit.get("_source") or {})
    raw_score = float(hit.get("_score") or 0.0)
    if score_scale == "cosine":
        score = max(-1.0, min(1.0, 2.0 * raw_score - 1.0))
    else:
        score = raw_score
    source["score"] = score
    source["source"] = score_scale
    return source


def _merge_hits(*hit_groups: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    active_groups = [hits for hits in hit_groups if hits]
    if not active_groups:
        return []

    merged: dict[str, dict[str, Any]] = {}
    for hits in active_groups:
        for rank, hit in enumerate(hits, start=1):
            table_id = str(hit.get("table_id") or "")
            if not table_id:
                continue
            current = merged.setdefault(
                table_id,
                {
                    "payload": dict(hit),
                    "rrf_score": 0.0,
                    "best_rank": rank,
                    "sources": [],
                },
            )
            current["rrf_score"] += 1.0 / (RRF_RANK_CONSTANT + rank)
            current["best_rank"] = min(int(current["best_rank"]), rank)
            source = str(hit.get("source") or "unknown")
            if source not in current["sources"]:
                current["sources"].append(source)

    max_rrf_score = len(active_groups) / (RRF_RANK_CONSTANT + 1)
    rows: list[dict[str, Any]] = []
    for item in merged.values():
        payload = dict(item["payload"])
        payload["score"] = (
            float(item["rrf_score"]) / max_rrf_score
            if max_rrf_score > 0
            else 0.0
        )
        payload["source"] = "rrf:" + "+".join(item["sources"])
        payload["_rrf_best_rank"] = int(item["best_rank"])
        rows.append(payload)

    rows.sort(
        key=lambda item: (
            -float(item.get("score") or 0.0),
            int(item.get("_rrf_best_rank") or 0),
            str(item.get("table_id") or ""),
        )
    )
    for item in rows:
        item.pop("_rrf_best_rank", None)
    return rows[: max(1, int(limit))]


table_search_index_service = TableSearchIndexService()
