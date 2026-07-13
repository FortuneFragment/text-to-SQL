from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import anyio
import pytest
from fastapi import HTTPException

from api.v1 import auth as auth_api
from core import auth as core_auth
from core.config import settings


def _configure_oauth(monkeypatch):
    monkeypatch.setattr(settings, "OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(
        settings,
        "OAUTH_REDIRECT_URI",
        "https://app.example.edu.cn/api/v1/auth/callback",
    )
    monkeypatch.setattr(
        settings,
        "OAUTH_LOGOUT_REDIRECT_URI",
        "https://app.example.edu.cn/api/v1/auth/logout/callback",
    )
    monkeypatch.setattr(
        settings,
        "FRONTEND_BASE_URL",
        "https://app.example.edu.cn",
    )


def test_login_rejects_incomplete_oauth_config(monkeypatch):
    monkeypatch.setattr(settings, "OAUTH_CLIENT_ID", "")
    monkeypatch.setattr(settings, "OAUTH_REDIRECT_URI", "")

    with pytest.raises(HTTPException) as exc_info:
        auth_api.login()

    assert exc_info.value.status_code == 503
    assert "配置不完整" in str(exc_info.value.detail)


def test_callback_rejects_failed_user_info_before_creating_session(
    monkeypatch,
):
    _configure_oauth(monkeypatch)
    monkeypatch.setattr(
        auth_api.redis_client,
        "getdel",
        lambda key: json.dumps({"next": "/chat"}),
    )

    async def fake_exchange_code(code):
        return {"access_token": "access-token", "x_unicode": "user-id"}

    async def fake_fetch_user_info(access_token):
        return {
            "code": "error",
            "state": False,
            "message": "token invalid",
            "data": None,
        }

    monkeypatch.setattr(auth_api, "exchange_code", fake_exchange_code)
    monkeypatch.setattr(auth_api, "fetch_user_info", fake_fetch_user_info)
    monkeypatch.setattr(
        auth_api.session_service,
        "create",
        lambda user_id: pytest.fail("失败响应不应创建会话"),
    )

    async def invoke_callback():
        with pytest.raises(HTTPException) as exc_info:
            await auth_api.callback(
                request=SimpleNamespace(cookies={"oauth_state": "state-value"}),
                code="authorization-code",
                state="state-value",
                db=object(),
            )
        return exc_info.value

    exc = anyio.run(invoke_callback)
    assert exc.status_code == 400
    assert "返回数据无效" in str(exc.detail)


def test_callback_preserves_legitimate_wrapped_login(monkeypatch):
    _configure_oauth(monkeypatch)
    monkeypatch.setattr(
        auth_api.redis_client,
        "getdel",
        lambda key: json.dumps({"next": "/chat"}),
    )

    async def fake_exchange_code(code):
        return {"access_token": "access-token", "x_unicode": "user-id"}

    async def fake_fetch_user_info(access_token):
        return {
            "code": "ok",
            "state": True,
            "message": "",
            "data": {
                "user": {
                    "uniCode": "user-id",
                    "name": "用户A",
                    "people": {"uniCode": "user-id", "roles": []},
                }
            },
        }

    saved = {}

    class FakeRepository:
        def upsert(self, **kwargs):
            saved.update(kwargs)
            return SimpleNamespace(id=7)

    monkeypatch.setattr(auth_api, "exchange_code", fake_exchange_code)
    monkeypatch.setattr(auth_api, "fetch_user_info", fake_fetch_user_info)
    monkeypatch.setattr(
        auth_api,
        "SystemUserRepository",
        lambda db: FakeRepository(),
    )
    monkeypatch.setattr(
        auth_api.session_service,
        "create",
        lambda user_id: "session-token",
    )

    async def invoke_callback():
        return await auth_api.callback(
            request=SimpleNamespace(cookies={"oauth_state": "state-value"}),
            code="authorization-code",
            state="state-value",
            db=object(),
        )

    response = anyio.run(invoke_callback)

    assert response.headers["location"] == "https://app.example.edu.cn/chat"
    assert "t2s_session=session-token" in response.headers["set-cookie"]
    assert saved["uni_code"] == "user-id"
    assert saved["name"] == "用户A"


def test_logout_sso_uses_explicit_registered_redirect(monkeypatch):
    _configure_oauth(monkeypatch)

    response = auth_api.logout_sso(
        SimpleNamespace(cookies={}),
    )

    location = response.headers["location"]
    query = parse_qs(urlparse(location).query)
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == [
        "https://app.example.edu.cn/api/v1/auth/logout/callback"
    ]


def test_logout_callback_lands_on_public_login(monkeypatch):
    _configure_oauth(monkeypatch)

    response = auth_api.logout_callback()

    assert response.headers["location"] == (
        "https://app.example.edu.cn/login?logged_out=1"
    )


def test_development_admin_login_has_admin_permission(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "ENABLE_DEV_LOGIN", True)

    assert core_auth.is_info_admin(object(), "dev-info-admin") is True
