from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

import core.connection_password_cipher as cipher_module
from schemas.text2sql import Text2SQLConnectionPayload
from services.text2sql.connection_service import Text2SQLConnectionService

connection_module = importlib.import_module("services.text2sql.connection_service")


class FakeConnectionRepo:
    active: SimpleNamespace | None = None

    def __init__(self, db):
        self.db = db

    def get_active(self):
        return self.__class__.active

    def upsert(self, **kwargs):
        payload = dict(kwargs)
        current = self.__class__.active
        if current is None:
            current = SimpleNamespace(**payload)
            self.__class__.active = current
        else:
            for key, value in payload.items():
                setattr(current, key, value)
        return current


def _build_payload(password: str | None = "abc123") -> Text2SQLConnectionPayload:
    return Text2SQLConnectionPayload(
        db_type="mysql",
        host="127.0.0.1",
        port=3306,
        username="root",
        password=password,
        database="biz_db",
        charset="utf8mb4",
    )


def test_save_connection_encrypts_password_and_runtime_uri_decrypts(monkeypatch):
    FakeConnectionRepo.active = None
    monkeypatch.setattr(connection_module, "Text2SQLConnectionRepository", FakeConnectionRepo)
    monkeypatch.setattr(cipher_module.settings, "APP_SECRET_KEY", "unit-test-app-secret")
    monkeypatch.setattr(cipher_module.settings, "FERNET_KEY", "")

    service = Text2SQLConnectionService()
    monkeypatch.setattr(service, "_test_uri", lambda uri: None)

    service.save_connection(db=object(), payload=_build_payload("abc123"))

    stored = FakeConnectionRepo.active
    assert stored is not None
    assert str(stored.password).startswith("enc:v1:")
    assert str(stored.password) != "abc123"

    runtime_uri = service._resolve_runtime_uri(db=object())
    assert "abc123@" in runtime_uri


def test_reusable_password_can_decrypt_encrypted_saved_password(monkeypatch):
    FakeConnectionRepo.active = None
    monkeypatch.setattr(connection_module, "Text2SQLConnectionRepository", FakeConnectionRepo)
    monkeypatch.setattr(cipher_module.settings, "APP_SECRET_KEY", "")
    monkeypatch.setattr(cipher_module.settings, "FERNET_KEY", Fernet.generate_key().decode("utf-8"))

    service = Text2SQLConnectionService()
    encrypted = service._password_cipher.encrypt("secret-pass")
    FakeConnectionRepo.active = SimpleNamespace(
        db_type="mysql",
        host="127.0.0.1",
        port=3306,
        username="root",
        password=encrypted,
        database="biz_db",
        charset="utf8mb4",
    )

    reused = service._resolve_reusable_password(
        db=object(),
        payload=_build_payload(password=None),
        empty_password_error="no password",
    )
    assert reused == "secret-pass"


def test_save_connection_requires_cipher_key(monkeypatch):
    FakeConnectionRepo.active = None
    monkeypatch.setattr(connection_module, "Text2SQLConnectionRepository", FakeConnectionRepo)
    monkeypatch.setattr(cipher_module.settings, "APP_SECRET_KEY", "")
    monkeypatch.setattr(cipher_module.settings, "FERNET_KEY", "")

    service = Text2SQLConnectionService()
    monkeypatch.setattr(service, "_test_uri", lambda uri: None)

    with pytest.raises(ValueError, match="FERNET_KEY|APP_SECRET_KEY"):
        service.save_connection(db=object(), payload=_build_payload("abc123"))


def test_public_connection_returns_unconfigured_without_saved_record(monkeypatch):
    FakeConnectionRepo.active = None
    monkeypatch.setattr(connection_module, "Text2SQLConnectionRepository", FakeConnectionRepo)
    monkeypatch.setattr(cipher_module.settings, "APP_SECRET_KEY", "unit-test-app-secret")
    monkeypatch.setattr(cipher_module.settings, "FERNET_KEY", "")

    service = Text2SQLConnectionService()
    result = service.get_public_connection(db=object())

    assert result.configured is False
