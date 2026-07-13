import json
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.auth import get_current_user, is_info_admin
from core.config import settings
from core.database import get_db
from core.redis_client import redis_client
from repositories.system_user_repo import SystemUserRepository
from services.auth.oauth_service import (
    build_authorize_url,
    exchange_code,
    fetch_user_info,
    normalize_profile,
)
from services.auth.session_service import session_service


router = APIRouter(prefix="/auth", tags=["auth"])


def normalize_next_path(value: str) -> str:
    if not value.startswith("/") or value.startswith("//"):
        return "/chat"
    return value


def require_oauth_config(*field_names: str) -> None:
    missing = [
        field_name
        for field_name in field_names
        if not str(getattr(settings, field_name, "") or "").strip()
    ]
    if missing:
        raise HTTPException(
            status_code=503,
            detail="统一认证配置不完整，请联系管理员",
        )


@router.get("/login")
def login(next: str = "/chat"):
    require_oauth_config(
        "OAUTH_CLIENT_ID",
        "OAUTH_REDIRECT_URI",
    )

    state = secrets.token_urlsafe(32)

    redis_client.setex(
        f"oauth:state:{state}",
        300,
        json.dumps(
            {"next": normalize_next_path(next)}
        ),
    )

    response = RedirectResponse(
        build_authorize_url(state)
    )

    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=300,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        path=f"{settings.API_V1_STR}/auth",
    )

    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    require_oauth_config(
        "OAUTH_CLIENT_ID",
        "OAUTH_CLIENT_SECRET",
        "OAUTH_REDIRECT_URI",
    )

    cookie_state = request.cookies.get("oauth_state")

    if not cookie_state or not secrets.compare_digest(
        cookie_state,
        state,
    ):
        raise HTTPException(
            status_code=400,
            detail="OAuth state 校验失败",
        )

    state_data = redis_client.getdel(
        f"oauth:state:{state}"
    )

    if not state_data:
        raise HTTPException(
            status_code=400,
            detail="OAuth state 无效或已过期",
        )

    try:
        token_data = await exchange_code(code)
        raw_profile = await fetch_user_info(
            token_data["access_token"]
        )

        token_user_code = str(
            token_data.get("x_unicode") or ""
        )

        profile = normalize_profile(
            raw_profile,
            expected_uni_code=token_user_code,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="统一认证服务暂时不可用，请稍后重试",
        ) from exc
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail="统一认证返回数据无效，请重新登录",
        ) from exc

    user = SystemUserRepository(db).upsert(
        uni_code=profile.uni_code,
        name=profile.name,
        email=profile.email,
        roles=profile.roles,
    )

    session_token = session_service.create(user.id)

    next_path = json.loads(state_data).get(
        "next",
        "/chat",
    )

    response = RedirectResponse(
        f"{settings.FRONTEND_BASE_URL.rstrip('/')}{next_path}"
    )

    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_token,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )

    response.delete_cookie(
        "oauth_state",
        path=f"{settings.API_V1_STR}/auth",
    )

    return response


@router.get("/me")
def me(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    admin = is_info_admin(
        db,
        current_user.uni_code,
    )

    return {
        "id": current_user.id,
        "uniCode": current_user.uni_code,
        "name": current_user.name,
        "role": (
            "info_admin"
            if admin
            else "chat_user"
        ),
        "permissions": (
            ["chat:use", "admin:access"]
            if admin
            else ["chat:use"]
        ),
    }


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get(
        settings.SESSION_COOKIE_NAME
    )

    if token:
        session_service.delete(token)

    response = JSONResponse({"ok": True})
    response.delete_cookie(
        settings.SESSION_COOKIE_NAME,
        path="/",
    )
    return response


@router.get("/logout/sso")
def logout_sso(request: Request):
    require_oauth_config(
        "OAUTH_CLIENT_ID",
        "OAUTH_LOGOUT_REDIRECT_URI",
    )

    token = request.cookies.get(
        settings.SESSION_COOKIE_NAME
    )

    if token:
        session_service.delete(token)

    query = urlencode(
        {
            "client_id": settings.OAUTH_CLIENT_ID,
            "redirect_uri": settings.OAUTH_LOGOUT_REDIRECT_URI,
            "state": "logout",
        }
    )

    response = RedirectResponse(
        f"{settings.OAUTH_LOGOUT_URL}?{query}"
    )

    response.delete_cookie(
        settings.SESSION_COOKIE_NAME,
        path="/",
    )

    return response


@router.get("/logout/callback")
def logout_callback():
    return RedirectResponse(
        f"{settings.FRONTEND_BASE_URL.rstrip('/')}"
        "/login?logged_out=1"
    )
