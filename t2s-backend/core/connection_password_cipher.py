from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings

_ENCRYPTED_PREFIX = "enc:v1:"


def _derive_fernet_key_from_app_secret(app_secret_key: str) -> bytes:
    digest = hashlib.sha256(app_secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _build_fernet() -> Fernet | None:
    raw_fernet_key = str(settings.FERNET_KEY or "").strip()
    if raw_fernet_key:
        return Fernet(raw_fernet_key.encode("utf-8"))

    app_secret_key = str(settings.APP_SECRET_KEY or "").strip()
    if app_secret_key:
        return Fernet(_derive_fernet_key_from_app_secret(app_secret_key))

    return None


class ConnectionPasswordCipher:
    def __init__(self):
        self._fernet = _build_fernet()

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        if self._fernet is None:
            raise ValueError("未配置 FERNET_KEY 或 APP_SECRET_KEY，无法加密连接密码")
        token = self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        return f"{_ENCRYPTED_PREFIX}{token}"

    def decrypt(self, ciphertext_or_plaintext: str) -> str:
        raw = str(ciphertext_or_plaintext or "").strip()
        if not raw:
            return ""
        if not raw.startswith(_ENCRYPTED_PREFIX):
            # Backward compatibility for historical plaintext rows.
            return raw
        if self._fernet is None:
            raise ValueError("未配置 FERNET_KEY 或 APP_SECRET_KEY，无法解密连接密码")
        token = raw[len(_ENCRYPTED_PREFIX) :]
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("连接密码解密失败，请检查 FERNET_KEY 或 APP_SECRET_KEY") from exc
