from __future__ import annotations

from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from core.url_utils import normalize_llm_base_url
from services.common.model_config_service import MODEL_KIND_LLM, model_config_service


class CommonLLMService:
    def __init__(self) -> None:
        self._model: ChatOpenAI | None = None
        self._model_key = ""

    def get_chat_model(self, db: Session | None = None, *, temperature: float = 0.0) -> ChatOpenAI | None:
        runtime = model_config_service.get_active_runtime_config(MODEL_KIND_LLM, db=db)
        if runtime is None:
            return None

        base_url = normalize_llm_base_url(runtime.base_url).rstrip("/")
        model_name = str(runtime.model_name or "").strip()
        if not (base_url and model_name):
            return None

        cache_key = f"{runtime.cache_key}|{float(temperature):.4f}"
        if self._model is not None and self._model_key == cache_key:
            return self._model

        self._model = ChatOpenAI(
            base_url=base_url,
            api_key=str(runtime.api_key or "").strip() or "EMPTY",
            model=model_name,
            temperature=max(0.0, float(temperature)),
            request_timeout=int(runtime.timeout_seconds),
            streaming=False,
        )
        self._model_key = cache_key
        return self._model


common_llm_service = CommonLLMService()
