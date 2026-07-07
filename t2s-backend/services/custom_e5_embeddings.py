from __future__ import annotations

from typing import List

import requests
from langchain_core.embeddings import Embeddings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CustomE5Embeddings(Embeddings):
    """对接兼容 OpenAI Embeddings 协议的向量服务。"""

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        batch_size: int = 32,
        verify_ssl: bool = True,
        ca_bundle: str | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        trust_env: bool = True,
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
        self.batch_size = max(1, int(batch_size))
        self.verify: bool | str = str(ca_bundle or "").strip() or bool(verify_ssl)
        self.session = requests.Session()
        self.session.trust_env = bool(trust_env)

        retries = max(0, int(max_retries))
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            allowed_methods=frozenset({"POST"}),
            status_forcelist=(429, 500, 502, 503, 504),
            backoff_factor=max(0.0, float(retry_backoff_seconds)),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

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
        try:
            response = self.session.post(
                self.api_url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.verify,
            )
            response.raise_for_status()
            body = response.json()
        except requests.exceptions.SSLError as exc:
            raise RuntimeError(
                "Embedding service SSL handshake failed. "
                "Please check the embedding model URL and certificate settings; "
                "for trusted internal endpoints you can disable SSL verification "
                "or provide a CA bundle in model config."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Embedding service request failed: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError("Embedding service returned invalid JSON") from exc

        data = body.get("data") or []
        return [item.get("embedding") or [] for item in data]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        normalized = [str(text or "") for text in texts]
        vectors: list[list[float]] = []
        for start in range(0, len(normalized), self.batch_size):
            batch = normalized[start : start + self.batch_size]
            vectors.extend(self._post_embeddings(batch))
        return vectors

    def embed_query(self, text: str) -> List[float]:
        query = str(text or "")
        vectors = self._post_embeddings([query])
        return vectors[0] if vectors else []
