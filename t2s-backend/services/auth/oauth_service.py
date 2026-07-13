from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from core.config import settings


@dataclass
class OAuthProfile:
    uni_code: str
    name: str
    email: str
    roles: list[dict]


def build_authorize_url(state: str) -> str:
    query = urlencode(
        {
            "client_id": settings.OAUTH_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
            "state": state,
        }
    )
    return f"{settings.OAUTH_AUTHORIZE_URL}?{query}"


async def exchange_code(code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            settings.OAUTH_TOKEN_URL,
            params={
                "client_id": settings.OAUTH_CLIENT_ID,
                "client_secret": settings.OAUTH_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.OAUTH_REDIRECT_URI,
            },
        )

        response.raise_for_status()
        payload = response.json()

    if not payload.get("access_token"):
        raise ValueError("OAuth 平台未返回 access_token")

    return payload


async def fetch_user_info(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            settings.OAUTH_USER_INFO_URL,
            params={
                "access_token": access_token,
                "grant_type": "user_info",
            },
        )

        response.raise_for_status()
        return response.json()


def normalize_profile(
    payload: dict[str, Any],
    expected_uni_code: str,
) -> OAuthProfile:
    if not isinstance(payload, dict):
        raise ValueError("OAuth 用户信息响应格式无效")

    # 学校门户返回包装结构；官方 user_info 文档则描述为原始用户对象。
    is_wrapped_response = "code" in payload and (
        "data" in payload
        or "message" in payload
        or isinstance(payload.get("state"), bool)
    )
    if is_wrapped_response:
        response_ok = (
            payload.get("state") is True
            and str(payload.get("code") or "").lower() == "ok"
        )
        if not response_ok:
            raise ValueError("OAuth 用户信息获取失败")

    data_value = payload.get("data")
    data = data_value if isinstance(data_value, dict) else {}

    root = (
        data.get("user")
        or data
        or payload.get("user")
        or payload
    )

    if not isinstance(root, dict):
        raise ValueError("OAuth 用户信息响应格式无效")

    people_value = root.get("people")
    people = people_value if isinstance(people_value, dict) else {}

    if not expected_uni_code:
        raise ValueError("OAuth Token 缺少 x_unicode")

    profile_uni_code = (
        root.get("uniCode")
        or people.get("uniCode")
        or payload.get("uniCode")
        or ""
    )

    if not profile_uni_code:
        raise ValueError("OAuth 用户信息缺少 uniCode")

    if str(profile_uni_code) != str(expected_uni_code):
        raise ValueError("OAuth 用户标识不一致")

    name = (
        root.get("name")
        or people.get("name")
        or payload.get("name")
        or ""
    )

    email = (
        root.get("email")
        or people.get("email")
        or payload.get("email")
        or ""
    )

    raw_roles_value = (
        root.get("roles")
        or people.get("roles")
        or payload.get("roles")
        or []
    )
    raw_roles = raw_roles_value if isinstance(raw_roles_value, list) else []

    roles = []

    for role in raw_roles:
        if not isinstance(role, dict):
            continue

        # 平台数据可能同时出现 organization 和拼写错误的 orgnization
        organization_value = (
            role.get("organization")
            or role.get("orgnization")
            or {}
        )
        organization = (
            organization_value
            if isinstance(organization_value, dict)
            else {}
        )
        role_type_value = role.get("type") or {}
        role_type = (
            role_type_value
            if isinstance(role_type_value, dict)
            else {}
        )

        roles.append(
            {
                "identity": str(role.get("identity") or ""),
                "organization": {
                    "uniCode": str(
                        organization.get("uniCode") or ""
                    ),
                    "code": str(
                        organization.get("code") or ""
                    ),
                    "name": str(
                        organization.get("name") or ""
                    ),
                    "fullName": str(
                        organization.get("fullName") or ""
                    ),
                },
                "type": {
                    "uniCode": str(
                        role_type.get("uniCode") or ""
                    ),
                    "code": str(
                        role_type.get("code") or ""
                    ),
                    "name": str(
                        role_type.get("name") or ""
                    ),
                },
            }
        )

    return OAuthProfile(
        uni_code=str(expected_uni_code),
        name=str(name),
        email=str(email),
        roles=roles,
    )
