from __future__ import annotations

import httpx

from core.url_utils import normalize_rerank_base_url
from services.common.model_config_service import MODEL_KIND_RERANK, model_config_service


class RerankerService:
    """Call the active rerank model config and return ranked document indexes."""

    def _resolve_reranker_config(self) -> tuple[bool, str, str, str]:
        runtime = model_config_service.get_active_runtime_config(MODEL_KIND_RERANK)
        if runtime is None:
            return False, "", "", ""
        return True, runtime.base_url, runtime.api_key, runtime.model_name

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        enabled, base_url, api_key, model = self._resolve_reranker_config()
        if not enabled or not base_url or not documents:
            return [(index, 1.0 / (index + 1)) for index in range(min(top_k, len(documents)))]
        return self._call_rerank_api(query, documents, top_k, base_url, api_key, model)

    def _call_rerank_api(
        self,
        query: str,
        documents: list[str],
        top_k: int,
        base_url: str,
        api_key: str,
        model: str,
    ) -> list[tuple[int, float]]:
        url = f"{normalize_rerank_base_url(base_url)}/v1/rerank"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": max(1, int(top_k)),
        }
        with httpx.Client(timeout=30) as client:
            response = client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(
                f"Reranker API returned error: status={response.status_code}, body={response.text[:200]}"
            )

        body = response.json()
        ranked = [
            (int(item["index"]), float(item["relevance_score"]))
            for item in body.get("results", [])
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[: max(1, int(top_k))]


reranker_service = RerankerService()
