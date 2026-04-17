from __future__ import annotations

from typing import List

import requests
from langchain_core.embeddings import Embeddings


class CustomE5Embeddings(Embeddings):
    """对接兼容 OpenAI Embeddings 协议的向量服务。"""

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        model: str,
        timeout: int = 60,
    ) -> None:
        base = str(api_base or "").strip().rstrip("/")
        if not base:
            raise ValueError("api_base is required")

        # Allow either .../v1 or direct .../embeddings endpoint.
        if base.endswith("/embeddings"):
            self.api_url = base
        elif base.endswith("/v1"):
            self.api_url = f"{base}/embeddings"
        else:
            self.api_url = base

        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.timeout = int(timeout)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post_embeddings(self, inputs: list[str]) -> list[list[float]]:
        payload = {
            "model": self.model,
            "input": inputs,
        }
        response = requests.post(
            self.api_url,
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        data = body.get("data") or []
        return [item.get("embedding") or [] for item in data]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self._post_embeddings([str(text or "") for text in texts])

    def embed_query(self, text: str) -> List[float]:
        query = str(text or "")
        vectors = self._post_embeddings([query])
        return vectors[0] if vectors else []
