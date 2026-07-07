from __future__ import annotations

import hashlib
import logging
import sys
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from core.connection_password_cipher import ConnectionPasswordCipher
from core.database import SessionLocal
from models.text2sql_model_config import Text2SQLModelConfig
from repositories.text2sql_model_config_repo import Text2SQLModelConfigRepository
from schemas.model_config import (
    ModelConfigActivationResponse,
    ModelConfigCreateRequest,
    ModelConfigResponse,
    ModelConfigUpdateRequest,
    ModelProviderInfo,
)

MODEL_KIND_LLM = "llm"
MODEL_KIND_EMBEDDING = "embedding"
MODEL_KIND_RERANK = "rerank"
SUPPORTED_MODEL_KINDS = {MODEL_KIND_LLM, MODEL_KIND_EMBEDDING, MODEL_KIND_RERANK}
SUPPORTED_MODEL_PROVIDERS = [
    {"provider": "openai", "display_name": "OpenAI", "supported_types": ["llm", "embedding"]},
    {"provider": "dashscope", "display_name": "阿里云通义", "supported_types": ["llm", "embedding", "rerank"]},
    {"provider": "zhipu", "display_name": "智谱AI", "supported_types": ["llm", "embedding"]},
    {"provider": "baichuan", "display_name": "百川AI", "supported_types": ["llm", "embedding"]},
    {"provider": "moonshot", "display_name": "月之暗面 Kimi", "supported_types": ["llm"]},
    {"provider": "deepseek", "display_name": "DeepSeek", "supported_types": ["llm"]},
    {"provider": "ollama", "display_name": "Ollama 本地", "supported_types": ["llm", "embedding"]},
    {"provider": "azure_openai", "display_name": "Azure OpenAI", "supported_types": ["llm", "embedding"]},
    {"provider": "anthropic", "display_name": "Anthropic Claude", "supported_types": ["llm"]},
    {"provider": "cohere", "display_name": "Cohere", "supported_types": ["llm", "embedding", "rerank"]},
    {"provider": "jina", "display_name": "Jina AI", "supported_types": ["embedding", "rerank"]},
    {"provider": "local", "display_name": "本地部署", "supported_types": ["llm", "embedding", "rerank"]},
    {"provider": "custom", "display_name": "自定义 OpenAI 兼容", "supported_types": ["llm", "embedding", "rerank"]},
]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeModelConfig:
    id: int
    kind: str
    name: str
    provider: str
    base_url: str
    api_key: str
    model_name: str
    timeout_seconds: int
    vector_dim: int | None
    batch_size: int | None
    verify_ssl: bool
    ca_bundle: str
    max_retries: int
    retry_backoff_seconds: float
    trust_env: bool
    extra_params: str
    updated_at: datetime | None

    @property
    def cache_key(self) -> str:
        api_key_hash = hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()[:16] if self.api_key else ""
        updated = self.updated_at.isoformat() if self.updated_at else ""
        return "|".join(
            [
                str(self.id),
                self.kind,
                self.provider,
                self.base_url,
                self.model_name,
                api_key_hash,
                str(self.timeout_seconds),
                str(self.vector_dim or ""),
                str(self.batch_size or ""),
                str(self.verify_ssl),
                self.ca_bundle,
                str(self.max_retries),
                str(self.retry_backoff_seconds),
                str(self.trust_env),
                self.extra_params,
                updated,
            ]
        )


class Text2SQLModelConfigService:
    def __init__(self) -> None:
        self._cipher = ConnectionPasswordCipher()

    @staticmethod
    def _normalize_kind(kind: str) -> str:
        normalized = str(kind or "").strip().lower()
        if normalized not in SUPPORTED_MODEL_KINDS:
            raise ValueError(f"Unsupported model config kind: {kind}")
        return normalized

    @staticmethod
    def _clean(value: object) -> str:
        return str(value or "").strip()

    def _encrypt_api_key(self, api_key: str | None, current_value: str = "") -> str:
        if api_key is None:
            return current_value
        cleaned = self._clean(api_key)
        if not cleaned:
            return ""
        return self._cipher.encrypt(cleaned)

    def _decrypt_api_key(self, stored_value: str | None) -> str:
        raw = self._clean(stored_value)
        if not raw:
            return ""
        return self._cipher.decrypt(raw)

    def _should_replace_api_key(self, api_key: str | None) -> bool:
        cleaned = self._clean(api_key)
        return bool(cleaned and "****" not in cleaned)

    @staticmethod
    def _mask_api_key(api_key: str) -> str:
        cleaned = str(api_key or "").strip()
        if not cleaned:
            return ""
        if len(cleaned) <= 8:
            return "****"
        return f"{cleaned[:4]}****{cleaned[-4:]}"

    def _to_response(self, entity: Text2SQLModelConfig) -> ModelConfigResponse:
        api_key = self._decrypt_api_key(entity.api_key)
        return ModelConfigResponse(
            id=int(entity.id),
            kind=str(entity.kind),
            model_type=str(entity.kind),
            name=str(entity.name),
            provider=str(entity.provider),
            base_url=str(entity.base_url),
            api_base_url=str(entity.base_url),
            model_name=str(entity.model_name),
            has_api_key=bool(self._clean(entity.api_key)),
            api_key_masked=self._mask_api_key(api_key),
            extra_params=entity.extra_params,
            timeout_seconds=int(entity.timeout_seconds),
            vector_dim=entity.vector_dim,
            batch_size=entity.batch_size,
            verify_ssl=bool(entity.verify_ssl),
            ca_bundle=entity.ca_bundle,
            max_retries=int(entity.max_retries),
            retry_backoff_seconds=float(entity.retry_backoff_seconds),
            trust_env=bool(entity.trust_env),
            is_active=bool(entity.is_active),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def list_configs(self, db: Session, kind: str | None = None) -> list[ModelConfigResponse]:
        normalized_kind = self._normalize_kind(kind) if kind else None
        rows = Text2SQLModelConfigRepository(db).list_all(normalized_kind)
        return [self._to_response(row) for row in rows]

    def get_config(self, db: Session, config_id: int) -> ModelConfigResponse:
        entity = Text2SQLModelConfigRepository(db).get_by_id(int(config_id))
        if entity is None:
            raise ValueError("Model config not found")
        return self._to_response(entity)

    def get_providers_info(self) -> list[ModelProviderInfo]:
        return [ModelProviderInfo(**item) for item in SUPPORTED_MODEL_PROVIDERS]

    def create_config(self, db: Session, payload: ModelConfigCreateRequest) -> ModelConfigResponse:
        kind = self._normalize_kind(payload.kind)
        entity = Text2SQLModelConfig(
            kind=kind,
            name=self._clean(payload.name),
            provider=self._clean(payload.provider) or "custom",
            base_url=self._clean(payload.base_url).rstrip("/"),
            api_key=self._encrypt_api_key(payload.api_key),
            model_name=self._clean(payload.model_name),
            extra_params=self._clean(payload.extra_params) or None,
            timeout_seconds=int(payload.timeout_seconds),
            vector_dim=(int(payload.vector_dim) if payload.vector_dim is not None else None),
            batch_size=(int(payload.batch_size) if payload.batch_size is not None else None),
            verify_ssl=bool(payload.verify_ssl),
            ca_bundle=self._clean(payload.ca_bundle) or None,
            max_retries=int(payload.max_retries),
            retry_backoff_seconds=float(payload.retry_backoff_seconds),
            trust_env=bool(payload.trust_env),
            is_active=False,
            is_deleted=False,
        )
        repo = Text2SQLModelConfigRepository(db)
        created = repo.create(entity)
        if payload.is_active:
            created = repo.activate(created)
            self._invalidate_service_cache(kind)
        return self._to_response(created)

    def update_config(
        self,
        db: Session,
        config_id: int,
        payload: ModelConfigUpdateRequest,
    ) -> ModelConfigResponse:
        repo = Text2SQLModelConfigRepository(db)
        entity = repo.get_by_id(int(config_id))
        if entity is None:
            raise ValueError("Model config not found")
        was_active = bool(entity.is_active)

        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            entity.name = self._clean(payload.name)
        if "provider" in updates:
            entity.provider = self._clean(payload.provider) or "custom"
        if "base_url" in updates:
            entity.base_url = self._clean(payload.base_url).rstrip("/")
        if "model_name" in updates:
            entity.model_name = self._clean(payload.model_name)
        if "api_key" in updates and self._should_replace_api_key(payload.api_key):
            entity.api_key = self._encrypt_api_key(payload.api_key, current_value=entity.api_key)
        if "extra_params" in updates:
            entity.extra_params = self._clean(payload.extra_params) or None
        if payload.timeout_seconds is not None:
            entity.timeout_seconds = int(payload.timeout_seconds)
        if "vector_dim" in updates:
            entity.vector_dim = int(payload.vector_dim) if payload.vector_dim is not None else None
        if "batch_size" in updates:
            entity.batch_size = int(payload.batch_size) if payload.batch_size is not None else None
        if payload.verify_ssl is not None:
            entity.verify_ssl = bool(payload.verify_ssl)
        if "ca_bundle" in updates:
            entity.ca_bundle = self._clean(payload.ca_bundle) or None
        if payload.max_retries is not None:
            entity.max_retries = int(payload.max_retries)
        if payload.retry_backoff_seconds is not None:
            entity.retry_backoff_seconds = float(payload.retry_backoff_seconds)
        if payload.trust_env is not None:
            entity.trust_env = bool(payload.trust_env)

        if entity.kind == MODEL_KIND_EMBEDDING:
            if not entity.batch_size:
                entity.batch_size = 32

        updated = repo.update(entity)
        if payload.is_active is True:
            updated = repo.activate(updated)
        elif payload.is_active is False and updated.is_active:
            updated.is_active = False
            updated = repo.update(updated)
        if was_active or updated.is_active:
            self._invalidate_service_cache(updated.kind)
        return self._to_response(updated)

    def activate_config(self, db: Session, config_id: int) -> ModelConfigActivationResponse:
        repo = Text2SQLModelConfigRepository(db)
        entity = repo.get_by_id(int(config_id))
        if entity is None:
            raise ValueError("Model config not found")
        old_active = repo.get_active(entity.kind)
        embedding_changed = entity.kind == MODEL_KIND_EMBEDDING and (
            old_active is None or int(old_active.id) != int(entity.id)
        )
        activated = repo.activate(entity)
        self._invalidate_service_cache(activated.kind)

        warning = None
        if embedding_changed:
            old_model = old_active.model_name if old_active else "None"
            warning = "Embedding 模型已切换，已有知识库向量数据需要重建后才能保证检索结果正确。"
            logger.warning("Embedding model changed: %s -> %s", old_model, activated.model_name)

        return ModelConfigActivationResponse(
            config=self._to_response(activated),
            warning=warning,
            needs_rebuild=embedding_changed,
        )

    def delete_config(self, db: Session, config_id: int) -> None:
        repo = Text2SQLModelConfigRepository(db)
        entity = repo.get_by_id(int(config_id))
        if entity is None:
            raise ValueError("Model config not found")
        if entity.is_active:
            raise ValueError("Active model config cannot be deleted")
        repo.soft_delete(entity)

    def _runtime_from_entity(self, entity: Text2SQLModelConfig) -> RuntimeModelConfig:
        return RuntimeModelConfig(
            id=int(entity.id),
            kind=str(entity.kind),
            name=str(entity.name),
            provider=str(entity.provider),
            base_url=str(entity.base_url or "").strip().rstrip("/"),
            api_key=self._decrypt_api_key(entity.api_key),
            model_name=str(entity.model_name or "").strip(),
            timeout_seconds=int(entity.timeout_seconds or 120),
            vector_dim=(int(entity.vector_dim) if entity.vector_dim is not None else None),
            batch_size=(int(entity.batch_size) if entity.batch_size is not None else None),
            verify_ssl=bool(entity.verify_ssl),
            ca_bundle=str(entity.ca_bundle or "").strip(),
            max_retries=int(entity.max_retries or 0),
            retry_backoff_seconds=float(entity.retry_backoff_seconds or 0.0),
            trust_env=bool(entity.trust_env),
            extra_params=str(entity.extra_params or "").strip(),
            updated_at=entity.updated_at,
        )

    def get_active_runtime_config(
        self,
        kind: str,
        db: Session | None = None,
    ) -> RuntimeModelConfig | None:
        normalized_kind = self._normalize_kind(kind)
        if db is not None:
            entity = Text2SQLModelConfigRepository(db).get_active(normalized_kind)
            return self._runtime_from_entity(entity) if entity is not None else None

        local_db = SessionLocal()
        try:
            entity = Text2SQLModelConfigRepository(local_db).get_active(normalized_kind)
            return self._runtime_from_entity(entity) if entity is not None else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("active model config lookup failed: kind=%s error=%s", normalized_kind, exc)
            return None
        finally:
            local_db.close()

    def get_active_model_name(self, kind: str, db: Session | None = None) -> str | None:
        runtime = self.get_active_runtime_config(kind, db=db)
        return runtime.model_name if runtime else None

    def get_active_config(self, db: Session, kind: str) -> Text2SQLModelConfig | None:
        return Text2SQLModelConfigRepository(db).get_active(self._normalize_kind(kind))

    @staticmethod
    def rebuild_all_knowledge_bases(db: Session) -> dict:
        from repositories.es_repo import es_repo
        from repositories.knowledge_base_repo import KnowledgeBaseRepository
        from repositories.knowledge_file_repo import KnowledgeFileRepository
        from tasks.document_tasks import reprocess_document_task

        kb_repo = KnowledgeBaseRepository(db)
        file_repo = KnowledgeFileRepository(db)
        all_kbs = kb_repo.list_all()

        total_files = 0
        for kb in all_kbs:
            try:
                es_repo.delete_chunks_by_kb_id(
                    int(kb.id),
                    index_name=str(kb.collection_name),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to drop Elasticsearch chunks for kb_id=%s: %s", kb.id, exc)

            page = 1
            while True:
                files, total = file_repo.list_by_kb_paginated(kb_id=int(kb.id), page=page, page_size=200)
                if not files:
                    break
                for file_entity in files:
                    if int(file_entity.status) == 2:
                        file_repo.update_status(int(file_entity.id), status=0, error_msg=None)
                        task = reprocess_document_task.delay(int(file_entity.id))
                        file_repo.set_task_id(int(file_entity.id), getattr(task, "id", None))
                        total_files += 1
                if page * 200 >= total:
                    break
                page += 1

        logger.info("Rebuild triggered: %s KBs, %s files queued", len(all_kbs), total_files)
        return {"total_kbs": len(all_kbs), "total_files": total_files}

    @staticmethod
    def _invalidate_service_cache(kind: str) -> None:
        try:
            if kind == MODEL_KIND_LLM:
                text2sql_module = sys.modules.get("services.text2sql")
                facade_service = getattr(text2sql_module, "facade_service", None)
                if facade_service is not None:
                    facade_service._model = None
                    facade_service._model_key = ""
                    facade_service._streaming_model = None
                    facade_service._streaming_model_key = ""
            elif kind == MODEL_KIND_EMBEDDING:
                embeddings_module = sys.modules.get("services.embeddings")
                reset_embeddings = getattr(embeddings_module, "reset_embeddings", None)
                if callable(reset_embeddings):
                    reset_embeddings()
        except Exception as exc:  # noqa: BLE001
            logger.warning("model service cache invalidation failed: kind=%s error=%s", kind, exc)


model_config_service = Text2SQLModelConfigService()
