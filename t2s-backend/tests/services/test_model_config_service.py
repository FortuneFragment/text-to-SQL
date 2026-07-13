from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.connection_password_cipher as cipher_module
from models.text2sql_model_config import Text2SQLModelConfig
from schemas.model_config import ModelConfigCreateRequest, ModelConfigUpdateRequest
from services.common.model_config_service import Text2SQLModelConfigService


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Text2SQLModelConfig.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def service(monkeypatch):
    monkeypatch.setattr(cipher_module.settings, "APP_SECRET_KEY", "unit-test-model-config-secret")
    monkeypatch.setattr(cipher_module.settings, "FERNET_KEY", "")
    return Text2SQLModelConfigService()


def test_model_config_encrypts_api_key_and_returns_runtime_secret(session, service):
    response = service.create_config(
        session,
        ModelConfigCreateRequest(
            kind="llm",
            name="main llm",
            base_url="https://llm.example.com/v1/",
            model_name="gpt-compatible",
            api_key="secret-key",
            is_active=True,
        ),
    )

    assert response.has_api_key is True
    assert response.model_type == "llm"
    assert response.api_base_url == "https://llm.example.com/v1"
    assert response.api_key_masked == "secr****-key"
    assert not hasattr(response, "api_key")

    stored = session.get(Text2SQLModelConfig, response.id)
    assert stored.api_key.startswith("enc:v1:")
    assert stored.api_key != "secret-key"

    runtime = service.get_active_runtime_config("llm", db=session)
    assert runtime is not None
    assert runtime.base_url == "https://llm.example.com/v1"
    assert runtime.api_key == "secret-key"
    assert runtime.model_name == "gpt-compatible"


def test_activate_config_keeps_one_active_per_kind(session, service):
    first = service.create_config(
        session,
        ModelConfigCreateRequest(
            kind="llm",
            name="first",
            base_url="https://one.example.com/v1",
            model_name="one",
            is_active=True,
        ),
    )
    second = service.create_config(
        session,
        ModelConfigCreateRequest(
            kind="llm",
            name="second",
            base_url="https://two.example.com/v1",
            model_name="two",
            is_active=True,
        ),
    )

    rows = service.list_configs(session, kind="llm")
    active_ids = [item.id for item in rows if item.is_active]

    assert first.id != second.id
    assert active_ids == [second.id]


def test_update_blank_or_masked_api_key_keeps_existing_secret(session, service):
    response = service.create_config(
        session,
        ModelConfigCreateRequest(
            kind="llm",
            name="main llm",
            base_url="https://llm.example.com/v1",
            model_name="gpt-compatible",
            api_key="secret-key",
            is_active=True,
        ),
    )

    service.update_config(session, response.id, ModelConfigUpdateRequest(api_key=""))
    assert service.get_active_runtime_config("llm", db=session).api_key == "secret-key"

    service.update_config(session, response.id, ModelConfigUpdateRequest(api_key="sk-****-key"))
    assert service.get_active_runtime_config("llm", db=session).api_key == "secret-key"

    service.update_config(session, response.id, ModelConfigUpdateRequest(api_key="new-secret"))
    assert service.get_active_runtime_config("llm", db=session).api_key == "new-secret"


def test_delete_active_config_is_rejected(session, service):
    response = service.create_config(
        session,
        ModelConfigCreateRequest(
            kind="llm",
            name="main llm",
            base_url="https://llm.example.com/v1",
            model_name="gpt-compatible",
            is_active=True,
        ),
    )

    with pytest.raises(ValueError, match="Active model config"):
        service.delete_config(session, response.id)


def test_rerank_config_and_provider_info_are_supported(session, service):
    response = service.create_config(
        session,
        ModelConfigCreateRequest(
            kind="rerank",
            name="reranker",
            provider="jina",
            base_url="https://rerank.example.com/v1",
            model_name="jina-reranker",
            is_active=True,
        ),
    )

    active = service.get_active_runtime_config("rerank", db=session)
    providers = service.get_providers_info()

    assert response.kind == "rerank"
    assert active is not None
    assert active.model_name == "jina-reranker"
    assert any("rerank" in item.supported_types for item in providers)


def test_reference_field_names_and_extra_params_are_supported(session, service):
    payload = ModelConfigCreateRequest(
        model_type="llm",
        name="reference style",
        provider="deepseek",
        api_base_url="https://api.deepseek.com/v1/chat/completions",
        model_name="deepseek-chat",
        api_key="deepseek-secret",
        extra_params='{"temperature":0}',
        is_active=True,
    )

    response = service.create_config(session, payload)
    runtime = service.get_active_runtime_config("llm", db=session)

    assert response.kind == "llm"
    assert response.model_type == "llm"
    assert response.base_url == "https://api.deepseek.com/v1/chat/completions"
    assert response.api_base_url == response.base_url
    assert response.extra_params == '{"temperature":0}'
    assert runtime.extra_params == '{"temperature":0}'

    updated = service.update_config(
        session,
        response.id,
        ModelConfigUpdateRequest(api_base_url="https://api.deepseek.com/v1", extra_params='{"top_p":1}'),
    )

    assert updated.base_url == "https://api.deepseek.com/v1"
    assert updated.extra_params == '{"top_p":1}'


def test_activate_embedding_returns_rebuild_warning(session, service):
    first = service.create_config(
        session,
        ModelConfigCreateRequest(
            kind="embedding",
            name="embed one",
            base_url="https://embedding-one.example.com/v1",
            model_name="e5-one",
            vector_dim=1024,
            is_active=True,
        ),
    )
    second = service.create_config(
        session,
        ModelConfigCreateRequest(
            kind="embedding",
            name="embed two",
            base_url="https://embedding-two.example.com/v1",
            model_name="e5-two",
            vector_dim=2048,
        ),
    )

    result = service.activate_config(session, second.id)

    assert first.id != second.id
    assert result.config.id == second.id
    assert result.needs_rebuild is True
    assert "Embedding" in result.warning


def test_embedding_config_allows_auto_detected_vector_dim(session, service):
    response = service.create_config(
        session,
        ModelConfigCreateRequest(
            kind="embedding",
            name="embed",
            base_url="https://embedding.example.com/v1/embeddings",
            model_name="e5",
            is_active=True,
        ),
    )

    runtime = service.get_active_runtime_config("embedding", db=session)

    assert response.vector_dim is None
    assert response.batch_size == 32
    assert runtime.vector_dim is None
